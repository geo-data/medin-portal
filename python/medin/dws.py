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
            results.append(('ff940020-1aa0-4abb-b9fc-c05c98eee863',
                            'Knock Deep Area TE 11 HI995',
                            'United Kingdom Hydrographic Office',
                            datetime.strptime('2009-05-20', '%Y-%m-%d')))

        return SearchResponse(hits, results, query)

class MetadataResponse(object):

    def __init__(self, gid, title, abstract, document):
        import libxml2
        
        self.id = gid
        self.title = title
        self.abstract = abstract

        try:
            self.document = libxml2.parseMemory(document, len(document))
        except libxml2.parserError, e:
            raise DWSError('The metadata document could not be parsed: %s' % str(e))

        xpath = self.xpath = self.document.xpathNewContext()
        xpath.xpathRegisterNs('gmd', 'http://www.isotc211.org/2005/gmd')
        xpath.xpathRegisterNs('gco', 'http://www.isotc211.org/2005/gco')

    def keywords(self):
        keywords = {}
        for node in self.xpath.xpathEval('//gmd:descriptiveKeywords/gmd:MD_Keywords'):
            self.xpath.setContextNode(node)
            try:
                words = self.xpath.xpathEval('./gmd:keyword/gco:CharacterString/text()')[0].content
            except IndexError:
                continue

            try:
                code = self.xpath.xpathEval('.//gmd:MD_KeywordTypeCode/@codeListValue')[0].content
            except IndexError:
                try:
                    code = self.xpath.xpathEval('.//gmd:title/gco:CharacterString/text()')[0].content 
                except IndexError:
                    code = 'general'

            try:
                keywords[code].append(words)
            except KeyError:
                keywords[code] = [words]

        self.xpath.setContextNode(self.document)

        return keywords

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

        gid = 'ff940020-1aa0-4abb-b9fc-c05c98eee863'
        title = 'Knock Deep Area TE 11 HI995'

        abstract = """SeaZone Digital Survey Bathymetry (DSB). Survey bathymetry data processed to form a
  dataset providing elevation at discrete points. The elevation and shape of the seabed."""

        document = """<?xml version="1.0" encoding="utf-8"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:gco="http://www.isotc211.org/2005/gco" xmlns:gmx="http://www.isotc211.org/2005/gmx" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://www.isotc211.org/2005/gmx ../XSD_Schemas/ISO_19139_Schemas/gmx/gmx.xsd">
  <gmd:fileIdentifier>
    <gco:CharacterString>ff940020-1aa0-4abb-b9fc-c05c98eee863</gco:CharacterString>
  </gmd:fileIdentifier>
  <!-- Metadata Language -->
  <gmd:language>
    <gmd:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/php/code_list.php" codeListValue="eng">English</gmd:LanguageCode>
  </gmd:language>
  <!-- Resource Type -->
  <gmd:hierarchyLevel>
    <gmd:MD_ScopeCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset">dataset</gmd:MD_ScopeCode>
  </gmd:hierarchyLevel>
  <!-- Metadata Point of Contact -->
  <gmd:contact>
    <gmd:CI_ResponsibleParty>
      <gmd:organisationName>
        <gco:CharacterString>SeaZone Solutions Limited</gco:CharacterString>
      </gmd:organisationName>
      <gmd:contactInfo>
        <gmd:CI_Contact>
          <gmd:phone>
            <gmd:CI_Telephone>
              <gmd:voice>
                <gco:CharacterString>0870 013 0607</gco:CharacterString>
              </gmd:voice>
            </gmd:CI_Telephone>
          </gmd:phone>
        </gmd:CI_Contact>
      </gmd:contactInfo>
      <gmd:role>
        <gmd:CI_RoleCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#CI_RoleCode" codeListValue="pointOfContact">pointOfContact</gmd:CI_RoleCode>
      </gmd:role>
    </gmd:CI_ResponsibleParty>
  </gmd:contact>
  <!-- Date of Update of Metadata -->
  <gmd:dateStamp>
    <gco:Date>2009-05-20</gco:Date>
  </gmd:dateStamp>
  <!-- Metadata Standard Name -->
  <gmd:metadataStandardName>
    <gco:CharacterString>MEDIN Discovery Metadata Standard</gco:CharacterString>
  </gmd:metadataStandardName>
  <!-- Metadata Standard Version -->
  <gmd:metadataStandardVersion>
    <gco:CharacterString>Version 2.3</gco:CharacterString>
  </gmd:metadataStandardVersion>
  <!-- Spatial Reference System - Recommend using EPSG URN -->
  <gmd:referenceSystemInfo>
    <gmd:MD_ReferenceSystem>
      <gmd:referenceSystemIdentifier>
        <gmd:RS_Identifier>
          <gmd:code>
            <gco:CharacterString>urn:ogc:def:crs:EPSG::4326</gco:CharacterString>
          </gmd:code>
          <gmd:codeSpace>
            <gco:CharacterString>OGP</gco:CharacterString>
          </gmd:codeSpace>
        </gmd:RS_Identifier>
      </gmd:referenceSystemIdentifier>
    </gmd:MD_ReferenceSystem>
  </gmd:referenceSystemInfo>
  <gmd:identificationInfo>
    <gmd:MD_DataIdentification id="szsl_dsb_100081">
      <gmd:citation>
        <gmd:CI_Citation>
          <!-- Resource Title -->
          <gmd:title>
            <gco:CharacterString>Knock Deep Area TE 11 HI995</gco:CharacterString>
          </gmd:title>
          <!-- Alternative Resource Title -->
          <gmd:alternateTitle>
            <gco:CharacterString>SeaZone Digital Survey Bathymetry</gco:CharacterString>
          </gmd:alternateTitle>
          <!-- Temporal Reference Date - Publication -->
          <gmd:date>
            <gmd:CI_Date>
              <gmd:date>
                <gco:Date>
       2005-11-16
      </gco:Date>
              </gmd:date>
              <gmd:dateType>
                <gmd:CI_DateTypeCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#CI_DateTypeCode" codeListValue="publication">publication</gmd:CI_DateTypeCode>
              </gmd:dateType>
            </gmd:CI_Date>
          </gmd:date>
          <!-- Unique Resource Identifier -->
          <gmd:identifier>
            <gmd:RS_Identifier>
              <gmd:code>
                <gco:CharacterString>100081</gco:CharacterString>
              </gmd:code>
              <gmd:codeSpace>
                <gco:CharacterString>http://www.seazone.com/dsb</gco:CharacterString>
              </gmd:codeSpace>
            </gmd:RS_Identifier>
          </gmd:identifier>
        </gmd:CI_Citation>
      </gmd:citation>
      <!-- Resource Abstract -->
      <gmd:abstract>
        <gco:CharacterString>
  SeaZone Digital Survey Bathymetry (DSB). Survey bathymetry data processed to form a
  dataset providing elevation at discrete points. The elevation and shape of the seabed.
</gco:CharacterString>
      </gmd:abstract>
      <!-- Data Point of Contact - Point of Contact -->
      <gmd:pointOfContact>
        <gmd:CI_ResponsibleParty>
          <gmd:organisationName>
            <gco:CharacterString>SeaZone Solutions Limited</gco:CharacterString>
          </gmd:organisationName>
          <gmd:contactInfo>
            <gmd:CI_Contact>
              <gmd:phone>
                <gmd:CI_Telephone>
                  <gmd:voice>
                    <gco:CharacterString>0870 013 0607</gco:CharacterString>
                  </gmd:voice>
                </gmd:CI_Telephone>
              </gmd:phone>
              <gmd:address>
                <gmd:CI_Address>
                  <gmd:deliveryPoint>
                    <gco:CharacterString>Red Lion House</gco:CharacterString>
                  </gmd:deliveryPoint>
                  <gmd:city>
                    <gco:CharacterString>Bentley</gco:CharacterString>
                  </gmd:city>
                  <gmd:postalCode>
                    <gco:CharacterString>GU10 5HY</gco:CharacterString>
                  </gmd:postalCode>
                  <gmd:country>
                    <gco:CharacterString>UK</gco:CharacterString>
                  </gmd:country>
                  <gmd:electronicMailAddress>
                    <gco:CharacterString>info@seazone.com</gco:CharacterString>
                  </gmd:electronicMailAddress>
                </gmd:CI_Address>
              </gmd:address>
            </gmd:CI_Contact>
          </gmd:contactInfo>
          <gmd:role>
            <gmd:CI_RoleCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#CI_RoleCode" codeListValue="pointOfContact">pointOfContact</gmd:CI_RoleCode>
          </gmd:role>
        </gmd:CI_ResponsibleParty>
      </gmd:pointOfContact>
      <!-- Data Point of Contact - Originator -->
      <gmd:pointOfContact>
        <gmd:CI_ResponsibleParty>
          <gmd:organisationName>
            <gco:CharacterString>United Kingdom Hydrographic Office</gco:CharacterString>
          </gmd:organisationName>
          <gmd:contactInfo>
            <gmd:CI_Contact>
              <gmd:phone>
                <gmd:CI_Telephone>
                  <gmd:voice>
                    <gco:CharacterString>+44 (0) 1823 337900</gco:CharacterString>
                  </gmd:voice>
                  <gmd:facsimile>
                    <gco:CharacterString>+44 (0) 1823 284077</gco:CharacterString>
                  </gmd:facsimile>
                </gmd:CI_Telephone>
              </gmd:phone>
              <gmd:address>
                <gmd:CI_Address>
                  <gmd:deliveryPoint>
                    <gco:CharacterString>Admiralty Way</gco:CharacterString>
                  </gmd:deliveryPoint>
                  <gmd:city>
                    <gco:CharacterString>Taunton</gco:CharacterString>
                  </gmd:city>
                  <gmd:postalCode>
                    <gco:CharacterString>TA1 2DN</gco:CharacterString>
                  </gmd:postalCode>
                  <gmd:country>
                    <gco:CharacterString>UK</gco:CharacterString>
                  </gmd:country>
                </gmd:CI_Address>
              </gmd:address>
            </gmd:CI_Contact>
          </gmd:contactInfo>
          <gmd:role>
            <gmd:CI_RoleCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#CI_RoleCode" codeListValue="originator">originator</gmd:CI_RoleCode>
          </gmd:role>
        </gmd:CI_ResponsibleParty>
      </gmd:pointOfContact>
      <!-- Frequency of Update -->
      <gmd:resourceMaintenance>
        <gmd:MD_MaintenanceInformation>
          <gmd:maintenanceAndUpdateFrequency>
            <gmd:MD_MaintenanceFrequencyCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#MD_MaintenanceFrequencyCode" codeListValue="notPlanned">notPlanned</gmd:MD_MaintenanceFrequencyCode>
          </gmd:maintenanceAndUpdateFrequency>
        </gmd:MD_MaintenanceInformation>
      </gmd:resourceMaintenance>
      <!-- Data Format -->
      <gmd:resourceFormat>
        <gmd:MD_Format>
          <gmd:name>
            <gco:CharacterString>
     Comma separated text. Longitude (Decimal Degrees), Latitude
     (Decimal Degrees), Elevation (Metres, positive up)
    </gco:CharacterString>
          </gmd:name>
          <gmd:version gco:nilReason="inapplicable"/>
        </gmd:MD_Format>
      </gmd:resourceFormat>
      <!-- Keyword - Proposal for NERC OAI Harvesting -->
      <gmd:descriptiveKeywords>
        <gmd:MD_Keywords>
          <gmd:keyword>
            <gmx:Anchor xlink:href="http://vocab.ndg.nerc.ac.uk/term/N010/0" xlink:title="NERC OAI Harvesting">NDGO0001</gmx:Anchor>
          </gmd:keyword>
        </gmd:MD_Keywords>
      </gmd:descriptiveKeywords>
      <!-- Keyword - for datasets claiming to be INSPIRE themes -->
      <gmd:descriptiveKeywords>
        <gmd:MD_Keywords>
          <gmd:keyword>
            <gco:CharacterString>BathyDep</gco:CharacterString>
          </gmd:keyword>
          <gmd:thesaurusName>
            <gmd:CI_Citation>
              <gmd:title>
                <gco:CharacterString>SeaDataNet BODC Vocabulary (P011)</gco:CharacterString>
              </gmd:title>
              <gmd:date>
                <gmd:CI_Date>
                  <gmd:date>
                    <gco:Date>2009-05-20</gco:Date>
                  </gmd:date>
                  <gmd:dateType>
                    <gmd:CI_DateTypeCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/Codelist/gmxCodelists.xml#CI_DateTypeCode" codeListValue="revision">revision</gmd:CI_DateTypeCode>
                  </gmd:dateType>
                </gmd:CI_Date>
              </gmd:date>
            </gmd:CI_Citation>
          </gmd:thesaurusName>
        </gmd:MD_Keywords>
      </gmd:descriptiveKeywords>
      <!-- Conditions Applying to Access and Use -->
      <gmd:resourceConstraints>
        <gmd:MD_Constraints>
          <gmd:useLimitation>
            <gco:CharacterString>Not suitable for navigation</gco:CharacterString>
          </gmd:useLimitation>
        </gmd:MD_Constraints>
      </gmd:resourceConstraints>
      <!-- Limitations on Public Access -->
      <gmd:resourceConstraints>
        <gmd:MD_LegalConstraints>
          <gmd:accessConstraints>
            <gmd:MD_RestrictionCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#MD_RestrictionCode" codeListValue="license">license</gmd:MD_RestrictionCode>
          </gmd:accessConstraints>
          <gmd:accessConstraints>
            <gmd:MD_RestrictionCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#MD_RestrictionCode" codeListValue="restricted">restricted</gmd:MD_RestrictionCode>
          </gmd:accessConstraints>
        </gmd:MD_LegalConstraints>
      </gmd:resourceConstraints>
      <!-- Spatial Resolution using representative fraction -->
      <gmd:spatialResolution>
        <gmd:MD_Resolution>
          <gmd:equivalentScale>
            <gmd:MD_RepresentativeFraction>
              <gmd:denominator>
                <gco:Integer>25000</gco:Integer>
              </gmd:denominator>
            </gmd:MD_RepresentativeFraction>
          </gmd:equivalentScale>
        </gmd:MD_Resolution>
      </gmd:spatialResolution>
      <!-- Resource Language -->
      <gmd:language>
        <gmd:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/php/code_list.php" codeListValue="eng">English</gmd:LanguageCode>
      </gmd:language>
      <!-- Topic Category -->
      <gmd:topicCategory>
        <gmd:MD_TopicCategoryCode>elevation</gmd:MD_TopicCategoryCode>
      </gmd:topicCategory>
      <gmd:topicCategory>
        <gmd:MD_TopicCategoryCode>oceans</gmd:MD_TopicCategoryCode>
      </gmd:topicCategory>
      <gmd:topicCategory>
        <gmd:MD_TopicCategoryCode>imageryBaseMapsEarthCover</gmd:MD_TopicCategoryCode>
      </gmd:topicCategory>
      <!-- Extent -->
      <gmd:extent>
        <gmd:EX_Extent>
          <gmd:geographicElement>
            <gmd:EX_GeographicDescription>
              <!-- Extent - by Identifier -->
              <gmd:geographicIdentifier>
                <gmd:MD_Identifier>
                  <gmd:authority>
                    <gmd:CI_Citation>
                      <gmd:title>
                        <gco:CharacterString>ICES Regions</gco:CharacterString>
                      </gmd:title>
                      <gmd:date>
                        <gmd:CI_Date>
                          <gmd:date>
                            <gco:Date>2006-01-01</gco:Date>
                          </gmd:date>
                          <gmd:dateType>
                            <gmd:CI_DateTypeCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#CI_DateTypeCode" codeListValue="revision">revision</gmd:CI_DateTypeCode>
                          </gmd:dateType>
                        </gmd:CI_Date>
                      </gmd:date>
                    </gmd:CI_Citation>
                  </gmd:authority>
                  <gmd:code>
                    <gco:CharacterString>IVc</gco:CharacterString>
                  </gmd:code>
                </gmd:MD_Identifier>
              </gmd:geographicIdentifier>
            </gmd:EX_GeographicDescription>
          </gmd:geographicElement>
          <!-- Geographic Bounding Box -->
          <gmd:geographicElement>
            <gmd:EX_GeographicBoundingBox>
              <gmd:westBoundLongitude>
                <gco:Decimal>1.42</gco:Decimal>
              </gmd:westBoundLongitude>
              <gmd:eastBoundLongitude>
                <gco:Decimal>1.69</gco:Decimal>
              </gmd:eastBoundLongitude>
              <gmd:southBoundLatitude>
                <gco:Decimal>51.57</gco:Decimal>
              </gmd:southBoundLatitude>
              <gmd:northBoundLatitude>
                <gco:Decimal>51.80</gco:Decimal>
              </gmd:northBoundLatitude>
            </gmd:EX_GeographicBoundingBox>
          </gmd:geographicElement>
          <!-- Temporal Extent -->
          <gmd:temporalElement>
            <gmd:EX_TemporalExtent>
              <gmd:extent>
                <gml:TimePeriod gml:id="ID1">
                  <gml:beginPosition>2002-05-02</gml:beginPosition>
                  <gml:endPosition>2002-05-09</gml:endPosition>
                </gml:TimePeriod>
              </gmd:extent>
            </gmd:EX_TemporalExtent>
          </gmd:temporalElement>
          <!-- Vertical Extent - Hard coded Vertical CRS Information -->
          <gmd:verticalElement>
            <gmd:EX_VerticalExtent>
              <gmd:minimumValue>
                <gco:Real>-30.7</gco:Real>
              </gmd:minimumValue>
              <gmd:maximumValue>
                <gco:Real>1.0</gco:Real>
              </gmd:maximumValue>
              <gmd:verticalCRS>
                <gml:VerticalCRS gml:id="metadata-crs-001">
                  <gml:identifier codeSpace="MEDIN">metadata-crs-001</gml:identifier>
                  <gml:name>Chart Datum Height</gml:name>
                  <gml:scope>Defines the vertical CRS of the minimum and maximum extent
values.</gml:scope>
                  <gml:verticalCS>
                    <gml:VerticalCS gml:id="metadata-cs-001">
                      <gml:identifier codeSpace="MEDIN">metadata-cs-001</gml:identifier>
                      <gml:name>Vertical coordinate system orientated up</gml:name>
                      <gml:axis>
                        <gml:CoordinateSystemAxis gml:id="metadata-axis-001" uom="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/uom/ gmxUom.xml#m">
                          <gml:identifier codeSpace="MEDIN">metadata-axis-001</gml:identifier>
                          <gml:axisAbbrev>Z</gml:axisAbbrev>
                          <gml:axisDirection codeSpace="MEDIN">up</gml:axisDirection>
                        </gml:CoordinateSystemAxis>
                      </gml:axis>
                    </gml:VerticalCS>
                  </gml:verticalCS>
                  <gml:verticalDatum>
                    <gml:VerticalDatum gml:id="metadata-datum-001">
                      <gml:identifier codeSpace="MEDIN">metadata-datum-001</gml:identifier>
                      <gml:name>Chart Datum</gml:name>
                      <gml:scope>Hydrographic survey and charting</gml:scope>
                      <gml:anchorDefinition>Approximation of Lowest Astronomical Tide at the local tide
station</gml:anchorDefinition>
                    </gml:VerticalDatum>
                  </gml:verticalDatum>
                </gml:VerticalCRS>
              </gmd:verticalCRS>
            </gmd:EX_VerticalExtent>
          </gmd:verticalElement>
        </gmd:EX_Extent>
      </gmd:extent>
    </gmd:MD_DataIdentification>
  </gmd:identificationInfo>
  <!-- Lineage -->
  <gmd:dataQualityInfo>
    <gmd:DQ_DataQuality>
      <!-- Scope - Required by ISO 19115 -->
      <gmd:scope>
        <gmd:DQ_Scope>
          <gmd:level>
            <gmd:MD_ScopeCode codeList="http://standards.iso.org/ittf/PubliclyAvailableStandards/ISO_19139_Schemas/resources/ Codelist/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset">dataset</gmd:MD_ScopeCode>
          </gmd:level>
        </gmd:DQ_Scope>
      </gmd:scope>
      <!-- Lineage -->
      <gmd:lineage>
        <gmd:LI_Lineage>
          <gmd:statement>
            <gco:CharacterString>
       Survey platform NP 1016. Horizontal datum of source
       data: World Geodetic System 1984. Vertical datum of source data: Lowest
       Astronomical Tide. Survey type: SINGLE BEAM.
      </gco:CharacterString>
          </gmd:statement>
        </gmd:LI_Lineage>
      </gmd:lineage>
    </gmd:DQ_DataQuality>
  </gmd:dataQualityInfo>
</gmd:MD_Metadata>
"""
        return MetadataResponse(gid, title, abstract, document)
