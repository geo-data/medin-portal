import os

# Third party modules
import suds                             # for the SOAP client

class DWSError(Exception):
    pass

class Query(object):
    """Stores OpenSearch query parameters"""

    def __init__(self, qsl=''):
        import cgi

        self.params = {}
        for k, v in cgi.parse_qsl(qsl):
            self.append(k, v)

    def __delitem__(self, k):
        del self.params[k]

    def __getitem__(self, k):
        return self.params[k]

    def __setitem__(self, k, v):
        """Sets the value of the FIRST item"""
        try:
            self.params[k][0] = v
        except KeyError:
            self.params[k] = [v]

    def __str__(self):
        from urllib import quote_plus
        params = []
        for k, v in self.params.items():
            for p in v:
                params.append('%s=%s' % (k, quote_plus(str(p))))

        return '&'.join(params)

    def append(self, k, v):
        try:
            self.params[k].append(v)
        except KeyError:
            self.params[k] = [v]

    def iterall(self):
        for k, v in self.params.iteritems():
            for p in v:
                yield (k, p)

class SearchQuery(Query):

    @property
    def search_term(self):
        try:
            return self['q']
        except KeyError:
            return []

    @property
    def sort(self):
        try:
            s = self['s'][0].split(',', 1)
        except KeyError, AttributeError:
            s = ('updated', '1')
            self['s'] = ','.join(s)
        
        try:
            field, asc = s
            asc = int(asc)
        except ValueError:
            del self['s']
            return (None, None)

        return field, asc

    @sort.setter
    def sort(self, value):
        self['s'] = ','.join((str(i) for i in value))

    @property
    def count(self):
        try:
            return int(self['c'][0])
        except KeyError:
            self['c'] = 20
            return self['c'][0]

    @count.setter
    def count(self, value):
        self['c'] = value

    @count.deleter
    def count(self):
        try:
            del self['c']
        except KeyError:
            pass

    @property
    def start_index(self):
        try:
            return int(self['i'][0])
        except KeyError:
            self['i'] = 1
            return self['i'][0]

    @start_index.setter
    def start_index(self, value):
        self['i'] = value

    @property
    def start_page(self):
        try:
            p = int(self['p'][0])
        except KeyError:
            p = self['p'] = 1
        if p > 500:
            p = self['p'] = 500

        return p

    @start_page.setter
    def start_page(self, value):
        self['p'] = value

class Request(object):

    def __init__(self, wsdl=None):
        if wsdl is None:     
            wsdl = 'file://%s' % os.path.join(os.path.dirname(__file__), 'data', 'dws.wsdl')

        self.client = suds.client.Client(wsdl)

    def __call__(query):
        raise NotImplementedError('The query must be overridden in a subclass')

class SearchResponse(object):

    def __init__(self, hits, results, query):
        from copy import deepcopy

        self.hits = hits
        self.results = results
        self.count = query.count
        self.search_term = query.search_term
        self.start_index = query.start_index - 1 # we use zero based indexing

        # set the index of the final result in this page
        self.end_index = self.start_index + self.count
        if self.end_index > hits:
            self.end_index = hits

        self.updated = max((r[-1] for r in results))
        if not self.updated:
            from datetime import datetime
            self.updated = datetime.utcnow()

        # The functionality from here down should move to the
        # medin.Result object

        #we make a copy as the query object is modified later
        self.query = deepcopy(query)

        self._setPageCounts()
        self._setFirstLink(query)
        self._setLastLink(query)
        self._setPrevLinks(query)
        self._setNextLinks(query)

        # bump the start index back to where people expect it to be
        self.start_index += 1

    def _setPageCounts(self):
        from math import ceil
        
        pages_before = self.start_index / float(self.count)
        self.current_page = int(ceil(pages_before)) + 1
        pages_after = (self.hits - self.start_index) / float(self.count)
        self.page_count = int(ceil(pages_before) + ceil(pages_after))

    def _setNextLinks(self, query):
        next_links = []
        next_index = self.start_index + self.count
        ic = 0
        page = self.current_page
        while page < self.page_count and ic < 5:
            page += 1
            ic += 1
            query.start_index = next_index + 1
            next_links.append({'page': page,
                               'link': str(query)})
            next_index += self.count
        self.next_links = next_links

    def _setLastLink(self, query):
        if self.current_page < self.page_count:
            query.start_index = 1 + self.start_index + (self.count * (self.page_count - self.current_page))
            self.last_link = {'page': self.page_count,
                              'link': str(query)}
        else:
            self.last_link = None

    def _setPrevLinks(self, query):
        prev_links = []
        prev_index = self.start_index - self.count
        ic = 0
        page = self.current_page
        while page > 1 and ic < 5:
            page -= 1
            ic += 1
            query.start_index = prev_index + 1
            prev_links.insert(0, {'page': page,
                                  'link': str(query)})
            prev_index -= self.count
        self.prev_links = prev_links

    def _setFirstLink(self, query):
        if self.current_page > 1:
            query.start_index = 1 + self.start_index - (self.count * (self.current_page-1))
            self.first_link = {'page': 1,
                               'link': str(query)}
        else:
            self.first_link = None

class Search(Request):
        
    def __call__(self, query):
        from datetime import datetime

        count = query.count
        search_term = ' '.join(query.search_term)

        # do a sanity check on the start index
        if query.start_index < (1 - count):
            query.start_index = 1
        
        # return some dummy data
        
        status = True
        message = 'Dummy failure'
        chars = len(''.join((c for c in search_term if not c.isspace())))
        hits = int(4000 / ((chars * (chars / 2.0)) + 1))

        if not status and not hits:
            raise DWSError('The Disovery Web Service failed: %s' % message)

        results = []

        start_index = query.start_index        
        if start_index < 1:
            c = count + start_index - 1
        elif count < hits:
            left = (hits - start_index) + 1
            if left < count:
                c = left
            else:
                c = count
        elif start_index > hits:
            c = 0
        else:
            c = hits
            
        for i in xrange(c):
            results.append(('b0de0599-5734-4946-b131-dfc65a16b1de',
                            'Broad Occupational Structure Map of Nepal',
                            'MENRIS, ICIMOD',
                            datetime.utcnow()))

        return SearchResponse(hits, results, query)

class MetadataResponse(object):

    def __init__(self, gid, title, abstract, document):
        self.id = gid
        self.title = title
        self.abstract = abstract
        self.document = document

class MetadataRequest(Request):

    def getMetadataFormats(self):
        response = self.client.service.getList('MetadataFormatList')
        return response.listMember
        
    def __call__(self, gid):
        # return some dummy data
        
        status = True
        message = 'Dummy failure'

        if not status:
            raise DWSError('The Disovery Web Service failed: %s' % message)

        gid = 'badc.nerc.ac.uk__DIF__dataent_claus.xml'
        title = 'Cloud Archive User Service data (CLAUS)'

        abstract = """Global Brightness Temperature imagery from the 
Cloud Archive User Service project. This project produced a long 
time-series of global thermal infra-red imagery of the Earth using 
data from operational meteorological satellites, which was used in 
validating atmospheric General Circulation Models"""

        document = """<?xml version="1.0" encoding="UTF-8"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:gts="http://www.isotc211.org/2005/gts" xmlns:gco="http://www.isotc211.org/2005/gco" xmlns:geonet="http://www.fao.org/geonetwork">
  <gmd:fileIdentifier>
    <gco:CharacterString xmlns:srv="http://www.isotc211.org/2005/srv">b0de0599-5734-4946-b131-dfc65a16b1de</gco:CharacterString>
  </gmd:fileIdentifier>
  <gmd:language>
    <gco:CharacterString>eng</gco:CharacterString>
  </gmd:language>
  <gmd:characterSet>
    <gmd:MD_CharacterSetCode codeListValue="utf8" codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_CharacterSetCode"/>
  </gmd:characterSet>
  <gmd:contact>
    <gmd:CI_ResponsibleParty>
      <gmd:individualName>
        <gco:CharacterString>Mr. Govinda Joshi</gco:CharacterString>
      </gmd:individualName>
      <gmd:organisationName>
        <gco:CharacterString>MENRIS, ICIMOD</gco:CharacterString>
      </gmd:organisationName>
      <gmd:positionName>
        <gco:CharacterString>Sr. Cartographer/GIS Analyst</gco:CharacterString>
      </gmd:positionName>
      <gmd:contactInfo>
        <gmd:CI_Contact>
          <gmd:phone>
            <gmd:CI_Telephone>
              <gmd:voice>
                <gco:CharacterString>977-1-5003222</gco:CharacterString>
              </gmd:voice>
              <gmd:facsimile>
                <gco:CharacterString>977-1-5003299</gco:CharacterString>
              </gmd:facsimile>
            </gmd:CI_Telephone>
          </gmd:phone>
          <gmd:address>
            <gmd:CI_Address>
              <gmd:deliveryPoint>
                <gco:CharacterString>Khumaltar</gco:CharacterString>
              </gmd:deliveryPoint>
              <gmd:city>
                <gco:CharacterString>Lalitpur</gco:CharacterString>
              </gmd:city>
              <gmd:administrativeArea>
                <gco:CharacterString>Kathmandu</gco:CharacterString>
              </gmd:administrativeArea>
              <gmd:postalCode>
                <gco:CharacterString>3226</gco:CharacterString>
              </gmd:postalCode>
              <gmd:country>
                <gco:CharacterString>Nepal</gco:CharacterString>
              </gmd:country>
              <gmd:electronicMailAddress>
                <gco:CharacterString>metadata@icimod.org</gco:CharacterString>
              </gmd:electronicMailAddress>
            </gmd:CI_Address>
          </gmd:address>
        </gmd:CI_Contact>
      </gmd:contactInfo>
      <gmd:role>
        <gmd:CI_RoleCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#CI_RoleCode" codeListValue="pointOfContact"/>
      </gmd:role>
    </gmd:CI_ResponsibleParty>
  </gmd:contact>
  <gmd:dateStamp>
    <gco:DateTime xmlns:srv="http://www.isotc211.org/2005/srv">2008-07-11T12:49:49</gco:DateTime>
  </gmd:dateStamp>
  <gmd:metadataStandardName>
    <gco:CharacterString xmlns:srv="http://www.isotc211.org/2005/srv">ISO 19115:2003/19139</gco:CharacterString>
  </gmd:metadataStandardName>
  <gmd:metadataStandardVersion>
    <gco:CharacterString xmlns:srv="http://www.isotc211.org/2005/srv">1.0</gco:CharacterString>
  </gmd:metadataStandardVersion>
  <gmd:referenceSystemInfo>
    <gmd:MD_ReferenceSystem>
      <gmd:referenceSystemIdentifier>
        <gmd:RS_Identifier>
          <gmd:code gco:nilReason="missing">
            <gco:CharacterString/>
          </gmd:code>
        </gmd:RS_Identifier>
      </gmd:referenceSystemIdentifier>
    </gmd:MD_ReferenceSystem>
  </gmd:referenceSystemInfo>
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification>
      <gmd:citation>
        <gmd:CI_Citation>
          <gmd:title>
            <gco:CharacterString>Broad Occupational Structure Map of Nepal</gco:CharacterString>
          </gmd:title>
          <gmd:alternateTitle gco:nilReason="missing">
            <gco:CharacterString/>
          </gmd:alternateTitle>
          <gmd:date>
            <gmd:CI_Date>
              <gmd:date>
                <gco:DateTime>2008-07-11T13:09:00</gco:DateTime>
              </gmd:date>
              <gmd:dateType>
                <gmd:CI_DateTypeCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#CI_DateTypeCode" codeListValue="publication"/>
              </gmd:dateType>
            </gmd:CI_Date>
          </gmd:date>
          <gmd:edition>
            <gco:CharacterString>First</gco:CharacterString>
          </gmd:edition>
          <gmd:identifier>
            <gmd:MD_Identifier>
              <gmd:code>
                <gco:CharacterString>np</gco:CharacterString>
              </gmd:code>
            </gmd:MD_Identifier>
          </gmd:identifier>
          <gmd:presentationForm>
            <gmd:CI_PresentationFormCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#CI_PresentationFormCode" codeListValue="mapDigital"/>
          </gmd:presentationForm>
        </gmd:CI_Citation>
      </gmd:citation>
      <gmd:abstract>
        <gco:CharacterString>The map was prepared based on CBS 1991 Data, showing Broad Occupational Structure of Nepal by district.</gco:CharacterString>
      </gmd:abstract>
      <gmd:purpose>
        <gco:CharacterString>The map was prepared under joint collaboration between ICIMOD/MENRIS and Central Bureau of Statistics (CBS), for the publication: Districts of Nepal, Indicators of Development Update 2003.</gco:CharacterString>
      </gmd:purpose>
      <gmd:status>
        <gmd:MD_ProgressCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_ProgressCode" codeListValue="completed"/>
      </gmd:status>
      <gmd:pointOfContact>
        <gmd:CI_ResponsibleParty>
          <gmd:individualName>
            <gco:CharacterString>Basanta Shrestha</gco:CharacterString>
          </gmd:individualName>
          <gmd:organisationName>
            <gco:CharacterString>MENRIS-ICIMOD</gco:CharacterString>
          </gmd:organisationName>
          <gmd:positionName>
            <gco:CharacterString>MENRIS, Division Head</gco:CharacterString>
          </gmd:positionName>
          <gmd:contactInfo>
            <gmd:CI_Contact>
              <gmd:phone>
                <gmd:CI_Telephone>
                  <gmd:voice>
                    <gco:CharacterString>977-1-5003222</gco:CharacterString>
                  </gmd:voice>
                  <gmd:facsimile>
                    <gco:CharacterString>977-1-5003299</gco:CharacterString>
                  </gmd:facsimile>
                </gmd:CI_Telephone>
              </gmd:phone>
              <gmd:address>
                <gmd:CI_Address>
                  <gmd:deliveryPoint>
                    <gco:CharacterString>Khumaltar</gco:CharacterString>
                  </gmd:deliveryPoint>
                  <gmd:city>
                    <gco:CharacterString>Lalitpur</gco:CharacterString>
                  </gmd:city>
                  <gmd:administrativeArea>
                    <gco:CharacterString>Kathmandu</gco:CharacterString>
                  </gmd:administrativeArea>
                  <gmd:postalCode>
                    <gco:CharacterString>3226</gco:CharacterString>
                  </gmd:postalCode>
                  <gmd:country>
                    <gco:CharacterString>Nepal</gco:CharacterString>
                  </gmd:country>
                  <gmd:electronicMailAddress>
                    <gco:CharacterString>metadata@icimod.org</gco:CharacterString>
                  </gmd:electronicMailAddress>
                </gmd:CI_Address>
              </gmd:address>
            </gmd:CI_Contact>
          </gmd:contactInfo>
          <gmd:role>
            <gmd:CI_RoleCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#CI_RoleCode" codeListValue="pointOfContact"/>
          </gmd:role>
        </gmd:CI_ResponsibleParty>
      </gmd:pointOfContact>
      <gmd:resourceMaintenance>
        <gmd:MD_MaintenanceInformation>
          <gmd:maintenanceAndUpdateFrequency>
            <gmd:MD_MaintenanceFrequencyCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_MaintenanceFrequencyCode" codeListValue="asNeeded"/>
          </gmd:maintenanceAndUpdateFrequency>
        </gmd:MD_MaintenanceInformation>
      </gmd:resourceMaintenance>
      <gmd:graphicOverview>
        <gmd:MD_BrowseGraphic>
          <gmd:fileName>
            <gco:CharacterString>snv19_s.png</gco:CharacterString>
          </gmd:fileName>
          <gmd:fileDescription>
            <gco:CharacterString>thumbnail</gco:CharacterString>
          </gmd:fileDescription>
          <gmd:fileType>
            <gco:CharacterString>png</gco:CharacterString>
          </gmd:fileType>
        </gmd:MD_BrowseGraphic>
      </gmd:graphicOverview>
      <gmd:graphicOverview>
        <gmd:MD_BrowseGraphic>
          <gmd:fileName>
            <gco:CharacterString>snv19.png</gco:CharacterString>
          </gmd:fileName>
          <gmd:fileDescription>
            <gco:CharacterString>large_thumbnail</gco:CharacterString>
          </gmd:fileDescription>
          <gmd:fileType>
            <gco:CharacterString>png</gco:CharacterString>
          </gmd:fileType>
        </gmd:MD_BrowseGraphic>
      </gmd:graphicOverview>
      <gmd:descriptiveKeywords>
        <gmd:MD_Keywords>
          <gmd:keyword>
            <gco:CharacterString>Broad Occupational structure</gco:CharacterString>
          </gmd:keyword>
          <gmd:type>
            <gmd:MD_KeywordTypeCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_KeywordTypeCode" codeListValue="theme"/>
          </gmd:type>
        </gmd:MD_Keywords>
      </gmd:descriptiveKeywords>
      <gmd:descriptiveKeywords>
        <gmd:MD_Keywords>
          <gmd:keyword>
            <gco:CharacterString>Nepal</gco:CharacterString>
          </gmd:keyword>
          <gmd:type>
            <gmd:MD_KeywordTypeCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_KeywordTypeCode" codeListValue="place"/>
          </gmd:type>
        </gmd:MD_Keywords>
      </gmd:descriptiveKeywords>
      <gmd:resourceConstraints>
        <gmd:MD_LegalConstraints>
          <gmd:accessConstraints>
            <gmd:MD_RestrictionCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_RestrictionCode" codeListValue="copyright"/>
          </gmd:accessConstraints>
          <gmd:useConstraints>
            <gmd:MD_RestrictionCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_RestrictionCode" codeListValue="otherRestrictions"/>
          </gmd:useConstraints>
          <gmd:otherConstraints>
            <gco:CharacterString>The content of this website can be accessed, printed and downloaded in an unaltered form (altered including being stretched, compressed, coloured or altered in any way so as to distort content from its original proportions or format) with copyright acknowledged, on a temporary basis for personal study that is not for a direct or indirect commercial use and any non-commercial use. Any content printed or downloaded may not be sold, licensed, transferred, copied or reproduced in whole or in part in any manner or in or on any media to any person without the prior written consent of the ICIMOD</gco:CharacterString>
          </gmd:otherConstraints>
        </gmd:MD_LegalConstraints>
      </gmd:resourceConstraints>
      <gmd:spatialRepresentationType>
        <gmd:MD_SpatialRepresentationTypeCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_SpatialRepresentationTypeCode" codeListValue="grid"/>
      </gmd:spatialRepresentationType>
      <gmd:spatialResolution>
        <gmd:MD_Resolution>
          <gmd:equivalentScale>
            <gmd:MD_RepresentativeFraction>
              <gmd:denominator>
                <gco:Integer>250000</gco:Integer>
              </gmd:denominator>
            </gmd:MD_RepresentativeFraction>
          </gmd:equivalentScale>
        </gmd:MD_Resolution>
      </gmd:spatialResolution>
      <gmd:language>
        <gco:CharacterString>eng</gco:CharacterString>
      </gmd:language>
      <gmd:characterSet>
        <gmd:MD_CharacterSetCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_CharacterSetCode" codeListValue="utf8"/>
      </gmd:characterSet>
      <gmd:topicCategory>
        <gmd:MD_TopicCategoryCode>economy</gmd:MD_TopicCategoryCode>
      </gmd:topicCategory>
      <gmd:extent>
        <gmd:EX_Extent>
          <gmd:temporalElement>
            <gmd:EX_TemporalExtent>
              <gmd:extent>
                <gml:TimePeriod gml:id="foo">
                  <gml:beginPosition/>
                  <gml:endPosition/>
                </gml:TimePeriod>
              </gmd:extent>
            </gmd:EX_TemporalExtent>
          </gmd:temporalElement>
        </gmd:EX_Extent>
      </gmd:extent>
      <gmd:extent>
        <gmd:EX_Extent>
          <gmd:geographicElement>
            <gmd:EX_GeographicBoundingBox>
              <gmd:westBoundLongitude>
                <gco:Decimal>80.0522</gco:Decimal>
              </gmd:westBoundLongitude>
              <gmd:eastBoundLongitude>
                <gco:Decimal>88.1946</gco:Decimal>
              </gmd:eastBoundLongitude>
              <gmd:southBoundLatitude>
                <gco:Decimal>26.3684</gco:Decimal>
              </gmd:southBoundLatitude>
              <gmd:northBoundLatitude>
                <gco:Decimal>30.4247</gco:Decimal>
              </gmd:northBoundLatitude>
            </gmd:EX_GeographicBoundingBox>
          </gmd:geographicElement>
        </gmd:EX_Extent>
      </gmd:extent>
      <gmd:supplementalInformation>
        <gco:CharacterString>Projection: UTM, Zone 44/45 (Spheroid Everest)
Base Map: Topographical Zonal Map (1:250,000), Topological Survey Branch, Department of Survey 1988.
Data: Population Census 1991</gco:CharacterString>
      </gmd:supplementalInformation>
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
  <gmd:distributionInfo>
    <gmd:MD_Distribution>
      <gmd:distributor>
        <gmd:MD_Distributor>
          <gmd:distributorContact>
            <gmd:CI_ResponsibleParty>
              <gmd:individualName>
                <gco:CharacterString>Mr. Govinda Joshi</gco:CharacterString>
              </gmd:individualName>
              <gmd:organisationName>
                <gco:CharacterString>MENRIS-ICIMOD</gco:CharacterString>
              </gmd:organisationName>
              <gmd:positionName>
                <gco:CharacterString>Sr. Cartographer/GIS Analyst</gco:CharacterString>
              </gmd:positionName>
              <gmd:contactInfo>
                <gmd:CI_Contact>
                  <gmd:phone>
                    <gmd:CI_Telephone>
                      <gmd:voice>
                        <gco:CharacterString>977-1-5003222</gco:CharacterString>
                      </gmd:voice>
                      <gmd:facsimile>
                        <gco:CharacterString>977-1-5003299</gco:CharacterString>
                      </gmd:facsimile>
                    </gmd:CI_Telephone>
                  </gmd:phone>
                  <gmd:address>
                    <gmd:CI_Address>
                      <gmd:deliveryPoint>
                        <gco:CharacterString>Khumaltar</gco:CharacterString>
                      </gmd:deliveryPoint>
                      <gmd:city>
                        <gco:CharacterString>Lalitpur</gco:CharacterString>
                      </gmd:city>
                      <gmd:administrativeArea>
                        <gco:CharacterString>Kathmandu</gco:CharacterString>
                      </gmd:administrativeArea>
                      <gmd:postalCode>
                        <gco:CharacterString>3226</gco:CharacterString>
                      </gmd:postalCode>
                      <gmd:country>
                        <gco:CharacterString>Nepal</gco:CharacterString>
                      </gmd:country>
                      <gmd:electronicMailAddress>
                        <gco:CharacterString>metadata@icimod.org</gco:CharacterString>
                      </gmd:electronicMailAddress>
                    </gmd:CI_Address>
                  </gmd:address>
                </gmd:CI_Contact>
              </gmd:contactInfo>
              <gmd:role>
                <gmd:CI_RoleCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#CI_RoleCode" codeListValue="distributor"/>
              </gmd:role>
            </gmd:CI_ResponsibleParty>
          </gmd:distributorContact>
        </gmd:MD_Distributor>
      </gmd:distributor>
      <gmd:transferOptions>
        <gmd:MD_DigitalTransferOptions>
          <gmd:onLine>
            <gmd:CI_OnlineResource>
              <gmd:linkage xmlns:srv="http://www.isotc211.org/2005/srv">
                <gmd:URL>http://arcsde.icimod.org.np:8080/geonetwork/srv/en/resources.get?id=277&amp;fname=snv19.jpg&amp;access=private</gmd:URL>
              </gmd:linkage>
              <gmd:protocol>
                <gco:CharacterString>WWW:DOWNLOAD-1.0-http--download</gco:CharacterString>
              </gmd:protocol>
              <gmd:name>
                <gco:CharacterString>snv19.jpg</gco:CharacterString>
              </gmd:name>
              <gmd:description gco:nilReason="missing">
                <gco:CharacterString/>
              </gmd:description>
            </gmd:CI_OnlineResource>
          </gmd:onLine>
        </gmd:MD_DigitalTransferOptions>
      </gmd:transferOptions>
    </gmd:MD_Distribution>
  </gmd:distributionInfo>
  <gmd:dataQualityInfo>
    <gmd:DQ_DataQuality>
      <gmd:scope>
        <gmd:DQ_Scope>
          <gmd:level>
            <gmd:MD_ScopeCode codeList="http://www.isotc211.org/2005/resources/codeList.xml#MD_ScopeCode" codeListValue="dataset"/>
          </gmd:level>
        </gmd:DQ_Scope>
      </gmd:scope>
      <gmd:lineage>
        <gmd:LI_Lineage>
          <gmd:statement>
            <gco:CharacterString>From Various Sources</gco:CharacterString>
          </gmd:statement>
        </gmd:LI_Lineage>
      </gmd:lineage>
    </gmd:DQ_DataQuality>
  </gmd:dataQualityInfo>
</gmd:MD_Metadata>
"""
        return MetadataResponse(gid, title, abstract, document)
