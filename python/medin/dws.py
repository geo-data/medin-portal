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
