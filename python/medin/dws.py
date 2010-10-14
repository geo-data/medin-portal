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

    def __call__(query, logger):
        raise NotImplementedError('The query must be overridden in a subclass')

    def _callService(self, logger, method, *args, **kwargs):
        """
        Wrap the call to the SOAP service with some error checking
        """
        from urllib2 import URLError
        
        try:
            return method(*args, **kwargs)
        except URLError, e:
            try:
                status, msg = e.reason
            except ValueError:
                status = 500

            msg = 'Connecting to the Discovery Web Service failed'
            logger.exception(msg)
            raise DWSError(msg, status)
        except Exception, e:
            msg = 'Data could not be retrieved as the Discovery Web Service failed'
            logger.exception(msg)
            try:
                status, reason = e.args[0]
            except (ValueError, IndexError):
                raise DWSError(msg)
            else:
                if status == 503:
                    msg = 'The Discovery Web Service is temorarily unavailable'
                raise DWSError(msg, status)


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

    def __call__(self, tokens, skip_errors=True):
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

            # If the term is a phrase ensure it is enclosed with two
            # pairs of quotes for the DWS
            if word.startswith('"') and word.endswith('"'):
                word = '""%s""' % word.strip('"')

            term = self.client.factory.create('ns0:SearchCriteria.TermSearch')
            term.Term = word
            try:
                term.TermTarget = self.targets[target.lower()]
            except KeyError:
                if not skip_errors:
                    raise ValueError('The following target is not recognised: %s' % target)
                term.TermTarget = self.targets['']
                
            term._id = i+1
            term._operator = op
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
        updated = datetime.strptime(i.DatasetUpdateDate, '%Y-%m-%d %H:%M:%S.%f')
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

        try:
            extent = doc.Spatial[0].BoundingBox
            bbox = [extent.LimitWest, extent.LimitSouth, extent.LimitEast, extent.LimitNorth]
        except AttributeError, IndexError:
            bbox = None

        ret = super(SummaryResponse, self)._processDocument(doc)
        ret['bbox'] = bbox
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

class SearchRequest(Request):

    _result_map = {RESULT_SIMPLE: SimpleResponse,
                   RESULT_BRIEF: BriefResponse,
                   RESULT_SUMMARY: SummaryResponse}

    def __call__(self, query, result_type, logger):
        try:
            ResponseClass = self._result_map[result_type]
        except KeyError:
            raise ValueError('Unknown result type: %s' % str(result_type))

        count = query.getCount()
        search_term = query.getSearchTerm(skip_errors=True)

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
        term_parser = TermBuilder(self.client)
        terms = term_parser(search_term)
        search.TermSearch.extend(terms)

        # add the spatial criteria
        aid = query.getArea(cast=False)
        if aid:
            bbox = query.areas.getBBOX(aid)
        else:
            bbox = query.getBBOX()
        if bbox:
            (search.SpatialSearch.BoundingBox.LimitWest,
             search.SpatialSearch.BoundingBox.LimitSouth,
             search.SpatialSearch.BoundingBox.LimitEast,
             search.SpatialSearch.BoundingBox.LimitNorth) = bbox
            search.SpatialSearch.SpatialOperator = 'Overlaps'

        # add the temporal criteria
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

        # send the query to the DWS
        response = ResponseClass(self._callService(logger,
                                                   self.client.service.doSearch,
                                                   search,
                                                   retrieve,
                                                   start_index,
                                                   dws_count),
                                 count)

        if not response:
            msg = 'Data could not be retrieved as the Discovery Web Service failed'
            logger.error(msg + ': %s' % response.message)
            raise DWSError(msg)

        return response

class MetadataRequest(Request):

    def getMetadataFormats(self, logger):
        response = self._callService(logger, self.client.service.getList, 'MetadataFormatList')

        return response.listMember
        
    def __call__(self, logger, gid, areas):
        """
        Connect to the DWS and retrieve a metadata entry by its ID
        """

        # construct the RetrieveCriteria
        retrieve = self.client.factory.create('ns0:RetrieveCriteriaType')
        retrieve.RecordDetail = 'DocumentFull' # we want all the info
        retrieve.MetadataFormat = 'MEDIN_2.3'

        # construct the SimpleDocument
        simpledoc = self.client.factory.create('ns0:SimpleDocument')
        simpledoc.DocumentId = gid
        
        # send the query to the DWS
        response = self._callService(logger, self.client.service.doPresent, [simpledoc], retrieve )
        
        status = response.Status
        message = response.StatusMessage

        if not status:
            msg = 'Data could not be retrieved as the Discovery Web Service failed'
            logger.error(msg + ': %s' % message)
            raise DWSError(msg)

        try:
            document = response.Documents.DocumentFull[0]
        except (AttributeError, IndexError):
            return None                 # no document found
        
        xml = document.Document

        # return a Metadata parser instance
        from metadata import Parser
        try:
            return Parser(gid, xml, areas)
        except ValueError, e:
            msg = 'The metadata does not appear to be valid'
            logger.exception(msg)
            raise DWSError(msg)
