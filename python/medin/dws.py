import os

# Third party modules
import suds                             # for the SOAP client

class DWSError(Exception):
    pass

class Request(object):

    def __init__(self, wsdl=None):
        if wsdl is None:     
            wsdl = 'file://%s' % os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'dws.wsdl'))

        self.client = suds.client.Client(wsdl, timeout=15)

    def __call__(query, logger):
        raise NotImplementedError('The query must be overridden in a subclass')

    def _callService(self, method, *args, **kwargs):
        """
        Wrap the call to the SOAP service with some error checking
        """

        try:
            return method(*args, **kwargs)
        except URLError, e:
            raise DWSError('The Discovery Web Service %s' % str(e.reason))
        except Exception, e:
            try:
                status, reason = e.args
            except ValueError:
                raise DWSError('The Discovery Web Service failed: %s' % str(e))
            else:
                if status == 503:
                    msg = 'The Discovery Web Service is temorarily unavailable'
                else:
                    msg = 'The Discovery Web Service failed: %s' % reason
                raise DWSError(msg)

class SearchResponse(object):

    def __init__(self, hits, results, query):
        from copy import deepcopy

        self.hits = hits
        self.results = results
        self.count = query.getCount()
        self.search_term = query.getSearchTerm(cast=False)
        self.start_index = query.getStartIndex() - 1 # we use zero based indexing

        # set the index of the final result in this page
        self.end_index = self.start_index + self.count
        if self.end_index > hits:
            self.end_index = hits

        try:
            self.updated = max((r[-2] for r in results))
        except ValueError:
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
            query.setStartIndex(next_index + 1)
            next_links.append({'page': page,
                               'link': str(query)})
            next_index += self.count
        self.next_links = next_links

    def _setLastLink(self, query):
        if self.current_page < self.page_count:
            query.setStartIndex(1 + self.start_index + (self.count * (self.page_count - self.current_page)))
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
            query.setStartIndex(prev_index + 1)
            prev_links.insert(0, {'page': page,
                                  'link': str(query)})
            prev_index -= self.count
        self.prev_links = prev_links

    def _setFirstLink(self, query):
        if self.current_page > 1:
            query.setStartIndex(1 + self.start_index - (self.count * (self.current_page-1)))
            self.first_link = {'page': 1,
                               'link': str(query)}
        else:
            self.first_link = None

class TermBuilder(object):
    """
    Build a list of DWS TermSearch objects from a token list
    """

    targets = {'': "FullText",
               'a': "Author",
               'p': "Parameters",
               'rt': "ResourceType",
               'tc': "TopicCategory",
               'l': "Lineage",
               'al': "PublicAccessLimits",
               'o': "DataOriginator",
               'f': "DataFormat"}

    def __init__(self, client):
        self.client = client

    def __call__(self, tokens):
        # If there aren't any tokens we need to do a full text search
        if not tokens:
            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.TermTarget = 'FullText'
            return [term]

        # Create the termSearch objects from the tokens
        terms = []
        for i, (op_or, op_not, target, word) in enumerate(tokens):
            op = ''
            if i:
                if op_or and op_not:
                    op = 'OR_NOT'
                elif op_not:
                    op ='AND_NOT'
                elif op_or:
                    op = 'OR'
            elif op_not:
                op = 'NOT'

            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = word
            try:
                term.TermTarget = self.targets[target.lower()]
            except KeyError:
                raise ValueError('The following target is not recognised: %s' % target)
                
            term._id = i+1
            term._operator = op
            terms.append(term)

        return terms

class SearchRequest(Request):
        
    def __call__(self, query, logger):
        from urllib2 import URLError
        from query import QueryError

        count = query.getCount()
        search_term = query.getSearchTerm()

        # do a sanity check on the start index
        if query.getStartIndex() < (1 - count):
            query.setStartIndex(1)

        # construct the RetrieveCriteria
        retrieve = self.client.factory.create('ns0:RetrieveCriteriaType')
        retrieve.RecordDetail = 'DocumentBrief' # we want brief results

        # construct the SearchCriteria
        search = self.client.factory.create('ns0:SearchCriteria')

        # add the terms
        term_parser = TermBuilder(self.client)
        terms = term_parser(search_term)
        search.TermSearch.extend(terms)

        # add the spatial criteria
        bbox = query.getBBOX()
        if bbox:
            (search.SpatialSearch.BoundingBox.LimitWest,
             search.SpatialSearch.BoundingBox.LimitSouth,
             search.SpatialSearch.BoundingBox.LimitEast,
             search.SpatialSearch.BoundingBox.LimitNorth) = bbox
            search.SpatialSearch.SpatialOperator = 'Overlaps'

        start = query.getStartDate()
        if start:
            start_date = self.client.factory.create('ns0:DateValueType')
            start_date.DateValue = start.strftime('%Y-%m-%d')
            start_date.TemporalOperator = "OnOrAfter"
            search.TemporalSearch.DateRange.Date.append(start_date)

        end = query.getEndDate()
        if end:
            end_date = self.client.factory.create('ns0:DateValueType')
            end_date.DateValue = end.strftime('%Y-%m-%d')
            end_date.TemporalOperator = "OnOrBefore"
            search.TemporalSearch.DateRange.Date.append(end_date)
        
        # send the query to the DWS
        response = self._callService(self.client.service.doSearch, search, retrieve, query.getStartIndex(), count )

        status = response.Status
        message = response.StatusMessage
        hits = response.Hits

        if not status:
            if message != 'Search was successful but generated no results.':
                raise DWSError('The Discovery Web Service failed: %s' % message)
            documents = []
        else:
            documents = response.Documents.DocumentBrief

        results = []
        from datetime import datetime
        for result in documents:
            fields = result.AdditionalInformation
            gid = result.DocumentId
            title = result.Title
            abstract = 'Test'
            originator = fields.DataOriginator
            date = datetime.now()
            bbox = [-180.0, -90.0, 180.0, 90]
            entry = (gid, title, originator, abstract, date, bbox)

            results.append(entry)

        return SearchResponse(hits, results, query)

# a decorator that ensures the xpath context is correct
def _assignContext(f):
    def newf(self):
        res = f(self)
        self.xpath.setContextNode(self.document)
        return res

    return newf

class MetadataResponse(object):

    def __init__(self, gid, title, abstract, document):
        import re
        import libxml2
        from terms import Vocabulary

        # instantiate the Vocabulary interface
        self.vocab = Vocabulary()
        
        self.id = gid
        self.title = title
        self.abstract = abstract

        try:
            self.document = libxml2.parseMemory(document, len(document))
        except libxml2.parserError, e:
            raise DWSError('The metadata document could not be parsed: %s' % str(e))

        # register the namespaces we need to search
        xpath = self.xpath = self.document.xpathNewContext()
        xpath.xpathRegisterNs('gmd', 'http://www.isotc211.org/2005/gmd')
        xpath.xpathRegisterNs('gco', 'http://www.isotc211.org/2005/gco')
        xpath.xpathRegisterNs('srv', 'http://www.isotc211.org/2005/srv')
        xpath.xpathRegisterNs('xlink', 'http://www.w3.org/1999/xlink')
        xpath.xpathRegisterNs('gml', 'http://www.opengis.net/gml/3.2')

        self._keyword_pattern = re.compile('\s*([A-Z]\d+)\s*')

    @property
    def author(self):
        try:
            return self.xpath.xpathEval("//gmd:CI_ResponsibleParty/gmd:role/gmd:CI_RoleCode[@codeListValue='originator']/../../gmd:organisationName/gco:CharacterString")[0].content
        except IndexError:
            return None

    def allElements(self):
        # Elements implemented according to
        # http://www.oceannet.org/marine_data_standards/medin_approved_standards/documents/medin_schema_documentation_2_3_2_10nov09.doc
        elements = [('Alternative resource title', self.alt_title),
                    ('Resource type', self.resource_type),
                    ('Unique resource identifier', self.unique_id),
                    ('Coupled resource', None), # TO BE IMPLEMENTED
                    ('Resource language', self.resource_language),
                    ('Spatial data service type', self.service_type),
                    ('Extent', self.extent),
                    ('Vertical extent information', self.vertical_extent),
                    ('Spatial reference system', self.srs),
                    ('Temporal reference', self.temporal_reference),
                    ('Lineage', self.lineage),
                    ('Spatial resolution', self.spatial_resolution),
                    ('Additional information source', self.additional_info),
                    ('Limitations on public access', self.access_limits),
                    ('Conditions for access and use constraints', self.access_conditions),
                    ('Responsible party', self.responsible_party),
                    ('Data format', self.data_format),
                    ('Frequency of update', self.update_frequency),
                    ('INSPIRE conformity', None), # TO BE IMPLEMENTED WHEN SPEC IS UPDATED
                    ('Date of update of metadata', self.metadata_update),
                    ('Metadata standard name', self.metadata_name),
                    ('Metadata standard version', self.metadata_version),
                    ('Metadata language', self.metadata_language)]

        details = []
        for name, method in elements:
            if not method:
                continue

            result = method()

            if result:
                details.append((name, result))

        return details

    def keywordListFromTitle(self, title):
        """
        Parse a keyword title and return the list key if present

        e.g. the title "SeaDataNet BODC Vocabulary (P011)" returns
        P011. A case insensitive match is also done on the title for
        the string 'inspire', in which case the code P220 is
        returned.
        """

        if 'inspire' in title.lower():
            return 'P220'
        
        match = self._keyword_pattern.search(title)
        if not match:
            return None

        return match.groups()[0]

    @_assignContext
    def keywords(self):
        keywords = {}
        for node in self.xpath.xpathEval('//gmd:descriptiveKeywords/gmd:MD_Keywords'):
            self.xpath.setContextNode(node)
            # try and retrieve the keyword
            try:
                words = self.xpath.xpathEval('./gmd:keyword/gco:CharacterString/text()')[0].content.strip()
            except IndexError:
                continue

            # try and get a code and a title for the list to which the
            # keyword belongs
            try:
                code = self.xpath.xpathEval('.//gmd:MD_KeywordTypeCode/@codeListValue')[0].content.strip()
                title = code
            except IndexError:
                try:
                    title = self.xpath.xpathEval('.//gmd:title/gco:CharacterString/text()')[0].content.strip()
                except IndexError:
                    code = 'unknown'
                    title = code
                else:
                    code = self.keywordListFromTitle(title)

            # try and get a definition for the term from the list code
            if code:
                try:
                    defn = self.vocab.lookupTerm(code, words)
                except LookupError:
                    defn = {}
            else:
                defn = {}

            # add the definition to the keyword dictionary
            try:
                keywords[title][words] = defn
            except KeyError:
                defns = {words: defn}
                keywords[title] = defns

        return keywords

    @_assignContext
    def online_resource(self):
        resources = []
        for node in self.xpath.xpathEval('//gmd:CI_OnlineResource'):
            resource = {}
            self.xpath.setContextNode(node)

            try:
                resource['link'] = self.xpath.xpathEval('./gmd:linkage/gmd:URL/text()')[0].content
            except IndexError:
                continue

            try:
                resource['name'] = self.xpath.xpathEval('./gmd:name/gmd:CharacterString/text()')[0].content
            except IndexError:
                resource['name'] = None

            try:
                resource['description'] = self.xpath.xpathEval('./gmd:description/gmd:CharacterString/text()')[0].content
            except IndexError:
                resource['description'] = None
            
            resources.append(resource)

        return resources

    def alt_title(self):
        titles = []
        for node in self.xpath.xpathEval('//gmd:alternateTitle/gco:CharacterString/text()'):
            titles.append(node.content)
        return titles

    def resource_type(self):
        types = {'attribute': 'Information applies to the attribute value',
                 'attributeType': 'Information applies to the characteristic of the feature',
                 'collectionHardware': 'Information applies to the collection hardware class',
                 'collectionSession': 'Information applies to the collection session',
                 'dataset': 'Information applies to a single dataset.',
                 'series': 'Information applies to a group of datasets linked by a common specification.',
                 'nonGeographicDataset': 'Information applies to the non geographic dataset.',
                 'dimensionGroup': 'Information applies to a dimension group',
                 'feature': 'Information applies to a feature',
                 'featureType': 'Information applies to a feature type',
                 'propertyType': 'Information applies to a property type',
                 'fieldSession': 'Information applies to a field session',
                 'software': 'Information applies to a computer program or routine',
                 'service': 'Information applies to a facility to view, download data e.g. web service',
                 'model': 'Information applies to a copy or imitation of an existing or hypothetical object',
                 'tile': 'Information applies to a tile, a spatial subset of geographic information'}

        try:
            code = self.xpath.xpathEval('//gmd:hierarchyLevel/gmd:MD_ScopeCode/text()')[0].content
        except IndexError:
            return []

        try:
            return [types[code]]
        except KeyError:
            return [code]

    def unique_id(self):
        ids = []
        for tag in ('MD_Identifier', 'RS_Identifier'):
            for node in self.xpath.xpathEval('//gmd:MD_DataIdentification//gmd:identifier/gmd:%s/gmd:code/gco:CharacterString/text()' % tag):
                ids.append(node.content)
        return ids

    def resource_language(self):
        langs = {'eng': 'English',
                 'cym': 'Welsh/Cymru',
                 'gle': 'Irish (Gaelic)',
                 'gla': 'Scottish (Gaelic)',
                 'cor': 'Cornish'}
        try:
            code = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode/@codeListValue')[0].content
        except IndexError:
            return []

        try:
            return [langs[code]]
        except KeyError:
            try:
                code = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode/text()')[0].content
            except IndexError:
                pass
            
        return [code]

    def topicCategory(self):
        categories = {}
        for node in self.xpath.xpathEval('//gmd:MD_TopicCategoryCode/text()'):
            try:
                defn = self.vocab.lookupTerm('P051', node.content)
            except LookupError:
                defn = {}
            categories[node.content] = defn

        return categories

    def service_type(self):
        types = []
        for node in self.xpath.xpathEval('//srv:SV_ServiceIdentification/srv:serviceType/gco:LocalName/text()'):
            types.append(node.content)
        return types

    def unique_id(self):
        ids = []
        for tag in ('MD_Identifier', 'RS_Identifier'):
            for node in self.xpath.xpathEval('//gmd:MD_DataIdentification//gmd:identifier/gmd:%s/gmd:code/gco:CharacterString/text()' % tag):
                ids.append(node.content)
        return ids

    @_assignContext
    def bbox(self):
        try:
            node = self.xpath.xpathEval('//gmd:EX_Extent/gmd:geographicElement/gmd:EX_GeographicBoundingBox')[0]
        except IndexError:
            return []
        self.xpath.setContextNode(node)
        
        ordinates = []

        for direction, latlon in (('west', 'longitude'), ('south', 'latitude'), ('east', 'longitude'), ('north', 'latitude')):
            try:
                
                ordinate = self.xpath.xpathEval('./gmd:%sBound%s/gco:Decimal/text()' % (direction, latlon.capitalize()))[0].content
            except IndexError:
                return []
            ordinates.append(float(ordinate))
            
        return ordinates

    @_assignContext
    def extent(self):
        extents = []
        for node in self.xpath.xpathEval('//gmd:geographicIdentifier/gmd:MD_Identifier'):
            self.xpath.setContextNode(node)
            try:
                title = self.xpath.xpathEval('./gmd:authority/gmd:CI_Citation/gmd:title/gco:CharacterString/text()')[0].content
            except IndexError:
                continue

            try:
                code = self.xpath.xpathEval('./gmd:code/gco:CharacterString/text()')[0].content
            except IndexError:
                continue
            
            extents.append('%s: %s' % (title, code))
        return extents

    @_assignContext
    def vertical_extent(self):
        try:
            node = self.xpath.xpathEval('//gmd:extent/gmd:EX_Extent/gmd:verticalElement/gmd:EX_VerticalExtent')[0]
        except IndexError:
            return []
        self.xpath.setContextNode(node)

        extents = []
        for text, xpath in (('Minimum Value', './gmd:minimumValue/gco:Real'),
                            ('Maximum Value', './gmd:maximumValue/gco:Real'),
                            ('Coordinate reference system', './gmd:verticalCRS/@xlink:href')):
            try:
                content = self.xpath.xpathEval(xpath)[0].content
            except IndexError:
                continue

            extents.append('%s: %s' % (text, content))

        try:
            node = self.xpath.xpathEval('./gmd:verticalCRS/gml:VerticalCRS')[0]
        except IndexError:
            return extents
        self.xpath.setContextNode(node)

        try:
            code = self.xpath.xpathEval('./gml:identifier/@codeSpace')[0].content
            idf = self.xpath.xpathEval('./gml:identifier/text()')[0].content
            extents.append('CRS identifier %s: %s' % (code, idf))
        except IndexError:
            pass

        try:
            name = self.xpath.xpathEval('./gml:name')[0].content
        except IndexError:
            pass
        else:
            extents.append('CRS name: %s' % name)

        try:
            scope = self.xpath.xpathEval('./gml:scope')[0].content
        except IndexError:
            pass
        else:
            extents.append('CRS scope: %s' % scope)

        try:
            code = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:identifier/@codeSpace')[0].content
            idf = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:identifier/text()')[0].content
            extents.append('CS identifier %s: %s' % (code, idf))
        except IndexError:
            pass

        try:
            name = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:name')[0].content
        except IndexError:
            pass
        else:
            extents.append('CS name: %s' % name)

        try:
            code = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:identifier/@codeSpace')[0].content
            idf = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:identifier/text()')[0].content
            extents.append('CS Axis identifier %s: %s' % (code, idf))
        except IndexError:
            pass

        try:
            abbrev = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:axisAbbrev/text()')[0].content
            direction = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:axisDirection/text()')[0].content
            extents.append('CS Axis is %s (%s)' % (abbrev, direction))
        except IndexError:
            pass
        
        try:
            code = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:identifier/@codeSpace')[0].content
            idf = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:identifier/text()')[0].content
            extents.append('Datum identifier %s: %s' % (code, idf))
        except IndexError:
            pass

        try:
            name = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:name')[0].content
        except IndexError:
            pass
        else:
            extents.append('Datum name: %s' % name)

        try:
            scope = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:scope')[0].content
        except IndexError:
            pass
        else:
            extents.append('Datum scope: %s' % scope)

        try:
            defn = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:anchorDefinition')[0].content
        except IndexError:
            pass
        else:
            extents.append('Datum definition: %s' % defn)

        return extents

    def srs(self):
        # get the SRS code
        try:
            code = self.xpath.xpathEval('//gmd:referenceSystemInfo/gmd:MD_ReferenceSystem/gmd:referenceSystemIdentifier/gmd:RS_Identifier/gmd:code/gco:CharacterString/text()')[0].content
        except IndexError:
            return ['Unknown spatial reference system']

        # get the XML corresponding to the code from the EPSG
        from urllib2 import urlopen, HTTPError
        epsg_url = 'http://www.epsg-registry.org/export.htm?gml=%s' % code

        try:
            res = urlopen(epsg_url)
        except HTTPError, e:
            return ['The reference system url at %s could not be opened: %s' % (epsg_url, str(e))]
        xml = res.read()

        # parse the XML
        import libxml2
        try:
            document = libxml2.parseMemory(xml, len(xml))
        except libxml2.parserError, e:
            return ['The reference system XML at %s could not be parsed: %s' % (epsg_url, str(e))]

        # register the namespaces we need to search
        xpath = document.xpathNewContext()
        xpath.xpathRegisterNs('gml', 'http://www.opengis.net/gml')

        details = ['Identifier: %s' % code,
                   'Source: <a href="%s" title="European Petroleum Survey Group">EPSG</a>' % epsg_url]
        try:
            name = xpath.xpathEval('//gml:*/gml:name')[0].content
            details.append('Name: %s' % name)
        except IndexError:
            pass

        try:
            scope = xpath.xpathEval('//gml:*/gml:scope')[0].content
            details.append('Scope: %s' % scope)
        except IndexError:
            pass

        return details

    def xsDate2pyDatetime(self, date):
        import datetime
        return datetime.datetime.strptime(date, '%Y-%m-%d')
        
    def formatDate(self, date):
        try:
            return self.xsDate2pyDatetime(date).strftime('%A %d %B %Y')
        except ValueError:
            return date

    def xsDatetime2pyDatetime(self, timestamp):
        import datetime
        return datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')
        
    def formatDatetime(self, timestamp):
        try:
            return self.xsDatetime2pyDatetime(timestamp).strftime('%A %d %B %Y at %H:%M:%S')
        except ValueError:
            return timestamp

    @_assignContext
    def temporal_reference(self):
        try:
            begin = self.xpath.xpathEval('//gmd:EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent//gml:beginPosition')[0].content
            end = self.xpath.xpathEval('//gmd:EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent//gml:endPosition')[0].content
        except IndexError:
            return []

        begin = self.formatDate(begin)
        end = self.formatDate(end)

        details = ['The data spans the period from %s to %s inclusive.' % (begin, end)]

        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:citation/gmd:CI_Citation/gmd:date/gmd:CI_Date'):
            self.xpath.setContextNode(node)
            try:
                date = self.xpath.xpathEval('./gmd:date/gco:Date')[0].content.strip()
            except IndexError:
                continue

            try:
                code = self.xpath.xpathEval('./gmd:dateType/gmd:CI_DateTypeCode')[0].content
            except IndexError:
                continue

            date = self.formatDate(date)
            details.append('%s date was %s' % (code.capitalize(), date))

        return details

    def lineage(self):
        try:
            lineage = self.xpath.xpathEval('//gmd:lineage/gmd:LI_Lineage/gmd:statement/gco:CharacterString')[0].content
        except IndexError:
            return []

        return [lineage]

    @_assignContext
    def spatial_resolution(self):
        details = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:spatialResolution/gmd:MD_Resolution'):
            self.xpath.setContextNode(node)
            
            try:
                distance = self.xpath.xpathEval('./gmd:distance/gco:Distance')[0].content
            except IndexError:
                pass
            else:
                details.append('Distance: %s meters' % distance)

            try:
                scale = self.xpath.xpathEval('./gmd:equivalentScale/gmd:MD_RepresentativeFraction/gmd:denominator')[0].content
            except IndexError:
                continue

            details.append('Scale: 1:%s' % scale)

        return details

    def additional_info(self):
        try:
            info = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:supplementalInformation/gco:CharacterString')[0].content
        except IndexError:
            return []

        return [info]

    def access_limits(self):
        codelist = {'copyright': 'Exclusive right to the publication, production, or sale of the rights to a literary, dramatic, musical, or artistic work, or to the use of a commercial print or label, granted by law for a specified period of time to an author, composer, artist, distributor',
                    'patent': 'Government has granted exclusive right to make, sell, use or license an invention or discovery.',
                    'patentPending': 'Produced or sold information awaiting a patent.',
                    'trademark': 'A name, symbol, or other device identifying a product, officially registered and legally restricted to the use of the owner or manufacturer.',
                    'license': 'Formal permission required to do something.',
                    'intellectualPropertyRights': 'Rights to financial benefit from and control of distribution of non-tangible property that is a result of creativity.',
                    'restricted': 'Withheld from general circulation or disclosure.'}

        details = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints/gmd:MD_RestrictionCode'):
            code = node.content
            try:
                details.append(codelist[code])
            except KeyError:
                if code != 'otherRestrictions':
                    details.append(code)

        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints/gmd:otherConstraints'):
            details.append(node.content)

        return details

    def access_conditions(self):
        details = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceConstraints/gmd:*/gmd:useLimitation'):
            details.append(node.content)

        return details

    def _contactDetails(self, node):
        roles = {'resourceProvider': 'Party that supplies the resource.',
                 'custodian': 'Party that accepts accountability and responsibility for the data and ensures appropriate care and maintenance of the resource.',
                 'owner': 'Party that owns the resource.',
                 'user': 'Party who uses the resource.',
                 'distributor': 'Party that distributes the resource.',
                 'originator': 'Party who created the resource.',
                 'pointOfContact': 'Party who can be contacted for acquiring knowledge about or acquisition of the resource.',
                 'principalInvestigator': 'Key party responsible for gathering information and conducting research.',
                 'processor': 'Party who has processed the data in a manner such that the resource has been modified.',
                 'publisher': 'Party who published the resource.',
                 'author': 'Party who authored the resource.'}
        
        details = []
        self.xpath.setContextNode(node)

        try:
            res = self.xpath.xpathEval('./gmd:positionName')[0].content
            details.append('Job position: %s' % res)
        except IndexError:
            pass

        try:
            res = self.xpath.xpathEval('./gmd:organisationName')[0].content
            details.append('Organisation: %s' % res)
        except IndexError:
            pass
        
        address = []
        for node in self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:address/gmd:CI_Address/gmd:deliveryPoint'):
            address.append(node.content.rstrip())

        for tag in ('city', 'postalCode', 'country'):
            try:
                res = self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:address/gmd:CI_Address/gmd:%s' % tag)[0].content
                address.append(res.rstrip())
            except IndexError:
                pass

        if address:
            details.append('Postal address: %s' % ', '.join(address))

        for medium, tag in (('Telephone', 'voice'), ('facsimile', 'Facsimile')):
            try:
                res = self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:phone/gmd:CI_Telephone/gmd:%s' % tag)[0].content
                details.append('%s: %s' % (medium, res))
            except IndexError:
                pass

        try:
            res = self.xpath.xpathEval('./gmd:contactInfo/gmd:address/gmd:CI_Address/gmd:electronicMailAddress')[0].content
            details.append('Email: <a href="mailto:%s">%s</a>' % (res, res))
        except IndexError:
            pass

        try:
            res = self.xpath.xpathEval('./gmd:role/gmd:CI_RoleCode')[0].content
        except IndexError:
            pass
        else:
            try:
                res = roles[res]
            except KeyError:
                pass
            details.append('Role: %s' % res)

        return "<br/>".join(details)

    @_assignContext
    def responsible_party(self):
        contacts = (('Metadata Point of Contact', '//gmd:MD_Metadata/gmd:contact/gmd:CI_ResponsibleParty'),
                    ('Originator', '//gmd:MD_Metadata/gmd:identificationInfo/gmd:MD_DataIdentification/gmd:pointOfContact/gmd:CI_ResponsibleParty'),
                    ('Distributor', '//gmd:MD_Metadata/gmd:distributionInfo/gmd:MD_Distribution/gmd:distributor/gmd:MD_Distributor/gmd:distributorContact/gmd:CI_ResponsibleParty'))
        parties = []
        for contact, xpath in contacts:
            details = []
            for node in self.xpath.xpathEval(xpath):
                details.append(self._contactDetails(node))

            if details:
                parties.append('<strong>%s:</strong>' % contact)
                parties += details
                
        return parties

    @_assignContext
    def data_format(self):
        formats = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceFormat/gmd:MD_Format'):
            self.xpath.setContextNode(node)
            try:
                name = self.xpath.xpathEval('./gmd:name/gco:CharacterString')[0].content
            except KeyError:
                continue

            try:
                version = self.xpath.xpathEval('./gmd:version/gco:CharacterString/text()')[0].content
                name += ' (version %s)' % version
            except IndexError:
                pass

            formats.append(name)

        return formats

    def update_frequency(self):
        codes = {'continual': 'Data is repeatedly and frequently updated',
                 'daily': 'Data is updated each day',
                 'weekly': 'Data is updated on a weekly basis',
                 'fortnightly': 'Data is updated every two weeks',
                 'monthly': 'Data is updated each month',
                 'quarterly': 'Data is updated every three months',
                 'biannually': 'Data is updated twice each year',
                 'annually': 'Data is updated every year',
                 'asNeeded': 'Data is updated as deemed necessary',
                 'irregular': 'Data is updated at intervals that are uneven in duration',
                 'notPlanned': 'There are no plans to update the data',
                 'unknown': 'Frequency of maintenance for the data is not known'}

        try:
            code = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceMaintenance/gmd:MD_MaintenanceInformation/gmd:maintenanceAndUpdateFrequency/gmd:MD_MaintenanceFrequencyCode/@codeListValue')[0].content
        except IndexError:
            return []

        try:
            return [codes[code]]
        except KeyError:
            return [code]

    def last_updated(self):
        try:
            return self._updated
        except AttributeError:
            pass

        try:
            date = self.xpath.xpathEval('/gmd:MD_Metadata/gmd:dateStamp/gco:Date')[0].content
        except IndexError:
            pass
        else:
            self._updated = self.formatDate(date)
            return self._updated

        try:
            datetime = self.xpath.xpathEval('/gmd:MD_Metadata/gmd:dateStamp/gco:DateTime')[0].content
        except IndexError:
            return ''
        self._updated = self.formatDatetime(datetime)
        return self._updated

    def metadata_update(self):
        return [self.last_updated()]
    
    def metadata_name(self):
        try:
            name = self.xpath.xpathEval('//gmd:MD_Metadata/gmd:metadataStandardName/gco:CharacterString')[0].content
        except IndexError:
            return []

        return [name]

    def metadata_version(self):
        try:
            version = self.xpath.xpathEval('//gmd:MD_Metadata/gmd:metadataStandardVersion/gco:CharacterString')[0].content
        except IndexError:
            return []

        return [version]
            
    def metadata_language(self):
        try:
            lang = self.xpath.xpathEval('//gmd:MD_Metadata/gmd:language/gmd:LanguageCode')[0].content
        except IndexError:
            return []

        return [lang]

class MetadataRequest(Request):

    def getMetadataFormats(self):
        from urllib2 import URLError

        response = self._callService(self.client.service.getList, 'MetadataFormatList')

        return response.listMember
        
    def __call__(self, gid):
        """
        Connect to the DWS and retrieve a metadata entry by its ID
        """

        from urllib2 import URLError

        # construct the RetrieveCriteria
        retrieve = self.client.factory.create('ns0:RetrieveCriteriaType')
        retrieve.RecordDetail = 'DocumentFull' # we want all the info
        retrieve.MetadataFormat = 'MEDIN_2.3'

        # construct the SimpleDocument
        simpledoc = self.client.factory.create('ns0:SimpleDocument')
        simpledoc.DocumentId = gid
        
        # send the query to the DWS
        response = self._callService(self.client.service.doPresent, [simpledoc], retrieve )
        
        status = response.Status
        message = response.StatusMessage

        if not status:
            if message != 'present.successful':
                raise DWSError('The Discovery Web Service failed: %s' % message)
            return None

        document = response.Documents.DocumentFull[0]
        title = document.Title
        abstract = document.Abstract
        xml = document.Document
        
        return MetadataResponse(gid, title, abstract, xml)
