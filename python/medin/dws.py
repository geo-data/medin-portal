# Created by Homme Zwaagstra
# 
# Copyright (c) 2010 GeoData Institute
# http://www.geodata.soton.ac.uk
# geodata@soton.ac.uk
# 
# Unless explicitly acquired and licensed from Licensor under another
# license, the contents of this file are subject to the Reciprocal
# Public License ("RPL") Version 1.5, or subsequent versions as
# allowed by the RPL, and You may not copy or use this file in either
# source code or executable form, except in compliance with the terms
# and conditions of the RPL.
# 
# All software distributed under the RPL is provided strictly on an
# "AS IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, AND LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES,
# INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, QUIET ENJOYMENT, OR
# NON-INFRINGEMENT. See the RPL for specific language governing rights
# and limitations under the RPL.
#
# You can obtain a full copy of the RPL from
# http://opensource.org/licenses/rpl1.5.txt or geodata@soton.ac.uk

import os

# Third party modules
import suds                             # for the SOAP client

RESULT_SIMPLE = 1
RESULT_BRIEF = 2
RESULT_SUMMARY = 3

class DWSError(Exception):

    def __init__(self, msg, status=500):
        self.status = status
        self.msg = msg

    def __str__(self):
        return self.msg

class Request(object):

    def __init__(self, wsdl=None):
        if wsdl is None:
            wsdl = 'file://%s' % os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'dws.wsdl'))

        self.client = suds.client.Client(wsdl, timeout=10)

    def __call__(self):
        try:
            caller = self.caller
        except AttributeError:
            raise RuntimeError('The request has been called before it has been prepared')

        return caller()

    def prepareCaller(self, *args, **kwargs):
        raise NotImplementedError('prepareCaller must be overridden in a subclass')


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
               'f': "AvailableDataFormats"}

    def __init__(self, client):
        self.client = client

    def __call__(self, tokens, parameters, data_holders, access_types, data_formats, skip_errors=True):
        # Create the termSearch objects from the tokens
        terms = []
        for i, token in enumerate(tokens):
            op = ''
            if i:
                if token.or_ and token.not_:
                    op = 'OR_NOT'
                elif token.not_:
                    op ='AND_NOT'
                elif token.or_:
                    op = 'OR'
            elif token.not_:
                op = 'NOT'

            word = token.word

            # If the term is a phrase ensure it is enclosed with two
            # pairs of quotes for the DWS
            if word.startswith('"') and word.endswith('"'):
                word = "'''%s'''" % word.strip('"')

            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = word
            try:
                term.TermTarget = self.targets[token.target.lower()]
            except KeyError:
                if not skip_errors:
                    raise ValueError('The following target is not recognised: %s' % token.target)
                term.TermTarget = self.targets['']

            term._id = i+1
            term._operator = op
            terms.append(term)

        # add parameters to the search terms
        if parameters:
            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = ' '.join(["'''%s'''" % param for param in parameters]) # `OR` query
            term.TermTarget = self.targets['p']
            if terms:
                term._operator = 'AND'
                term._id = len(terms) + 1
            else:
                term._id = 1
            terms.append(term)

        # add data holders to the search terms
        if data_holders:
            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = ' '.join(["'''%s'''" % holder for holder in data_holders]) # `OR` query
            term.TermTarget = self.targets['o']
            if terms:
                term._operator = 'AND'
                term._id = len(terms) + 1
            else:
                term._id = 1
            terms.append(term)

        # add access types to the search terms
        if access_types:
            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = ' '.join(["'''%s'''" % type_.prefLabel for type_ in access_types]) # `OR` query
            term.TermTarget = self.targets['al']
            if terms:
                term._operator = 'AND'
                term._id = len(terms) + 1
            else:
                term._id = 1
            terms.append(term)

        # add data formats to the search terms
        if data_formats:
            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = ' '.join(["'''%s'''" % fmt.prefLabel for fmt in data_formats]) # `OR` query
            term.TermTarget = self.targets['f']
            if terms:
                term._operator = 'AND'
                term._id = len(terms) + 1
            else:
                term._id = 1
            terms.append(term)

        # If there aren't any tokens we need to do a full text search
        if not terms:
            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.TermTarget = 'FullText'
            terms.append(term)

        return terms

class SearchResponse(object):
    """
    Interface to DWS search responses

    An Abstract class providing an interface to a Response as returned
    by the DWS
    """

    doc_type = None                     # the DWS document request type

    def __init__(self, reply, count):
        self.reply = reply              # the raw DWS reply
        self.count = count

    @property
    def message(self):
        return self.reply.StatusMessage

    @property
    def hits(self):
        return self.reply.Hits

    def _processDocument(self, doc):
        return doc

    def __nonzero__(self):
        """
        Return True if the response is valid, False otherwise
        """
        return self.reply.Status

    def __len__(self):
        if self and self.hits:
            return len(getattr(self.reply.Documents, self.doc_type))
        return 0

    def __iter__(self):
        if self and self.hits:
            docs = getattr(self.reply.Documents, self.doc_type)
        else:
            docs = []

        for doc in docs:
            yield self._processDocument(doc)

class SimpleResponse(SearchResponse):

    doc_type = 'DocumentSimple'

    def _processDocument(self, doc):
        return doc.DocumentId

class BriefResponse(SearchResponse):

    doc_type = 'DocumentBrief'

    def lastModified(self):
        """
        Last modification date for the response
        """

        # the last modification date is the most recent date in the
        # results
        try:
            return max((r['updated'] for r in self))
        except ValueError:
            from datetime import datetime
            return datetime.utcnow()

    # this function needs to be modified when the DWS has been fixed
    # to return the correct fields
    def _processDocument(self, doc):
        from datetime import datetime

        def to_list(field):
            if hasattr(field, 'split'):
                return [e.strip() for e in field.split(';')]
            return []

        i = doc.AdditionalInformation
        if i.DatasetUpdateDate:
            updated = datetime.strptime(i.DatasetUpdateDate, '%Y-%m-%d %H:%M:%S.%f')
        else:
            updated = datetime.utcnow() # only happens with bad DWS responses

        return {'id': doc.DocumentId,
                'title': doc.Title,
                'updated': updated,
                'authors': to_list(i.Authors),
                'resource-type': i.ResourceType,
                'topic-category': i.TopicCategory,
                'lineage': i.Lineage,
                'public-access': i.LimitationsPublicAccess,
                'originator': i.DataOriginator,
                'format': i.OriginalFormatName,
                'parameters': to_list(i.Parameters)}

class SummaryResponse(BriefResponse):

    doc_type = 'DocumentSummary'

    def _processDocument(self, doc):

        bboxes = []
        try:
            extents = doc.Spatial
        except AttributeError:
            pass
        else:
            for extent in extents:
                try:
                    extent = extent.BoundingBox
                    bboxes.append([extent.LimitWest, extent.LimitSouth, extent.LimitEast, extent.LimitNorth])
                except (AttributeError, IndexError):
                    pass

        ret = super(SummaryResponse, self)._processDocument(doc)
        ret['bbox'] = bboxes
        ret['abstract'] = doc.Abstract

        return ret

class OrderAnalyser(object):
    """
    Receives and verifies sorting input from the query
    """

    _field_map = {'updated': 'DatasetMetadataUpdateDate',
                  'title': 'DiscoveryTitle',
                  'originator': 'DataCenter'}

    def __init__(self, field, ascending):
        try:
            self.field = self._field_map[field]
        except KeyError:
            raise ValueError('Unknown sort field: %s. Choose one of %s.' % (field, ', '.join(self._field_map.keys())))

        if ascending:
            self.direction = 'ascending'
        else:
            self.direction = 'descending'

class SOAPCaller(object):
    """
    An object that handles a calls to the SOAP service

    Each caller handles a specific request to a SOAP service method
    using a client and calling arguments.
    """

    def __init__(self, client, soap_method, logger, *args, **kwargs):
        self.client = client
        self.method = getattr(client.service, soap_method)
        self.logger = logger
        self.args = args
        self.kwargs = kwargs

    def requestXML(self):
        """
        Return the SOAP Envelope for the request
        """

        self.client.set_options(nosend=True)
        try:
            req = self()
        finally:
            self.client.set_options(nosend=False)

        return req.envelope

    def responseXML(self):
        """
        Return the SOAP Envelope for the response
        """

        self.client.set_options(retxml=True)
        try:
            xml = self()
        finally:
            self.client.set_options(retxml=False)

        return xml

    def __call__(self):
        """
        Wrap the call to the SOAP service with some error checking
        """
        from urllib2 import URLError

        try:
            return self.method(*(self.args), **(self.kwargs))
        except URLError, e:
            try:
                status, msg = e.reason
            except ValueError:
                status = 500
                msg = 'Connecting to the Discovery Web Service failed: %s' % e.reason

            self.logger.error(msg)
            raise DWSError(msg, status)
        except Exception, e:
            msg = 'Data could not be retrieved as the Discovery Web Service failed'
            self.logger.exception(msg)
            try:
                status, reason = e.args[0]
            except (ValueError, IndexError):
                raise DWSError(msg)
            else:
                if status == 503:
                    msg = 'The Discovery Web Service is temorarily unavailable'
                raise DWSError(msg, status)

class SearchRequest(Request):

    _result_map = {RESULT_SIMPLE: SimpleResponse,
                   RESULT_BRIEF: BriefResponse,
                   RESULT_SUMMARY: SummaryResponse}

    def prepareCaller(self, query, result_type, logger):
        try:
            ResponseClass = self._result_map[result_type]
        except KeyError:
            raise ValueError('Unknown result type: %s' % str(result_type))

        count = query.getCount()
        search_term = query.getSearchTerm(default=[], skip_errors=True)
        
        # do a sanity check on the start index
        if query.getStartIndex() < (1 - count):
            query.setStartIndex(1)

        # construct the RetrieveCriteria
        retrieve = self.client.factory.create('ns0:RetrieveCriteriaType')
        retrieve.RecordDetail = ResponseClass.doc_type

        # add the ordering criteria
        order_by = self.client.factory.create('ns0:OrderByType')
        order = query.getSort()
        if not order:
            field = 'DatasetMetadataUpdateDate'
            direction = 'descending'
        else:
            analyser = OrderAnalyser(*order)
            field = analyser.field
            direction = analyser.direction

        order_by.OrderByField = field
        order_by.OrderByDirection = direction
        retrieve.OrderBy.append(order_by)

        # construct the SearchCriteria
        search = self.client.factory.create('ns0:SearchCriteria')

        # add the terms
        parameters = query.getParameterLabels()
        data_holders = query.getDataHolders(default=[])
        access_types = query.getAccessTypes(default=[])
        data_formats = query.getDataFormats(default=[])
        term_parser = TermBuilder(self.client)
        terms = term_parser(search_term, parameters, data_holders, access_types, data_formats)
        search.TermSearch.extend(terms)

        # add the spatial criteria
        aid = query.getArea(cast=False)
        boxes = []
        if aid:
            bbox = query.areas.getBBOX(aid)
            if bbox:
                boxes.append(bbox)
        else:
            boxes.extend(query.getBoxes())

        if boxes:
            # get the total extent, as the DWS does not currently
            # support multiple bounding boxes
            bbox = [
                min((box[0] for box in boxes)),
                min((box[1] for box in boxes)),
                max((box[2] for box in boxes)),
                max((box[3] for box in boxes))]

            (search.SpatialSearch.BoundingBox.LimitWest,
             search.SpatialSearch.BoundingBox.LimitSouth,
             search.SpatialSearch.BoundingBox.LimitEast,
             search.SpatialSearch.BoundingBox.LimitNorth) = bbox
            search.SpatialSearch.SpatialOperator = 'Overlaps'

        # add the temporal criteria
        start = query.getStartDate()
        if start:
            start_date = self.client.factory.create('ns0:DateValueType')
            start_date.DateValue = start.date().isoformat()
            start_date.TemporalOperator = "OnOrAfter"
            search.TemporalSearch.DateRange.Date.append(start_date)

        end = query.getEndDate()
        if end:
            end_date = self.client.factory.create('ns0:DateValueType')
            end_date.DateValue = end.date().isoformat()
            end_date.TemporalOperator = "OnOrBefore"
            search.TemporalSearch.DateRange.Date.append(end_date)

        if search.TemporalSearch.DateRange.Date:
            search.TemporalSearch.DateRange.DateRangeTarget = 'TemporalCoverage'

        # work around the fact that the DWS can't be asked to return
        # zero results and it can't deal with a negative start index
        start_index = query.getStartIndex()
        if start_index < 1:
            if count != 0:
                # the count needs to be adjusted for negative start index
                dws_count = count - (abs(start_index) + 1)
            else:
                # the count is zero so needs to be set to one
                dws_count = 1
            start_index = 1
        elif count > 0:
            # the count is fine, leave as is
            dws_count = count
        else:
            # the count is zero so needs to be set to one
            dws_count = 1

        self.caller = SOAPCaller(self.client,
                                 'doSearch',
                                 logger,
                                 search,
                                 retrieve,
                                 start_index,
                                 dws_count)
        self.count = count
        self.ResponseClass = ResponseClass
        self.logger = logger

        return self.caller

    def __call__(self):
        result = super(SearchRequest, self).__call__()

        # send the query to the DWS
        response = self.ResponseClass(result, self.count)

        if not response:
            msg = 'Data could not be retrieved as the Discovery Web Service failed'
            self.logger.error(msg + ': %s' % response.message)
            raise DWSError(msg)

        return response

class MetadataResponse(object):
    """
    Interface to DWS metadata response

    An class providing a more user friendly interface to a full
    doPresent Response as returned by the DWS
    """

    def __init__(self, reply):
        self.reply = reply              # the raw DWS reply

    @property
    def message(self):
        return self.reply.StatusMessage

    @property
    def xml(self):
        try:
            return str(self.reply.Documents.DocumentFull[0].Document)
        except (AttributeError, IndexError):
            return None                 # no document found

    @property
    def gid(self):
        try:
            return self.reply.Documents.DocumentFull[0].DocumentId
        except (AttributeError, IndexError):
            return None                 # no document found

    @property
    def date(self):
        """Last update date"""
        try:
            return self.reply.Documents.DocumentFull[0].AdditionalInformation.DatasetUpdateDate
        except (AttributeError, IndexError):
            return None                 # no document found

    def __nonzero__(self):
        """
        Return True if the response is valid, False otherwise
        """
        return self.reply.Status

class MetadataRequest(Request):

    def getMetadataFormats(self, logger):
        caller = SOAPCaller(self.client, 'getList', logger, 'MetadataFormatList')
        response = caller()

        return response.listMember

    def prepareCaller(self, logger, gid, format):
        # construct the RetrieveCriteria
        retrieve = self.client.factory.create('ns0:RetrieveCriteriaType')
        retrieve.RecordDetail = 'DocumentFull' # we want all the info
        retrieve.MetadataFormat = format

        # construct the SimpleDocument
        simpledoc = self.client.factory.create('ns0:SimpleDocument')
        simpledoc.DocumentId = gid

        # send the query to the DWS
        self.caller = SOAPCaller(self.client,
                                 'doPresent',
                                 logger,
                                 [simpledoc],
                                 retrieve)
        self.gid = gid
        self.logger = logger
        return self.caller

    def __call__(self):
        """
        Connect to the DWS and retrieve a metadata entry by its ID
        """

        response = super(MetadataRequest, self).__call__()
        response = MetadataResponse(response) # wrap the response in our more accessible object

        if not response:
            msg = 'Data could not be retrieved as the Discovery Web Service failed'
            self.logger.error(msg + ': %s' % response.message)
            raise DWSError(msg)

        return response

class MedinMetadataRequest(MetadataRequest):

    def prepareCaller(self, logger, gid, areas, vocab):
        # get a document in MEDIN XML format
        format = 'MEDIN_2.3'

        self.areas = areas
        self.vocab = vocab
        return super(MedinMetadataRequest, self).prepareCaller(logger, gid, format)

    def __call__(self):
        response = super(MedinMetadataRequest, self).__call__()

        xml = response.xml
        if xml is None:
            return None

        # return a Metadata parser instance
        from metadata import Parser
        try:
            return Parser(self.gid, xml, self.areas, self.vocab)
        except ValueError, e:
            msg = 'The metadata does not appear to be valid'
            self.logger.exception(msg)
            raise DWSError(msg)
