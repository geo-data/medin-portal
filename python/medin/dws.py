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
                params.append('%s=%s' % (k, quote_plus(p)))

        return '&'.join(params)

    def append(self, k, v):
        try:
            self.params[k].append(v)
        except KeyError:
            self.params[k] = [v]

class SearchQuery(Query):

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

    def __init__(self, hits, results, count, start_page, start_index):
        self.hits = hits
        self.results = results
        self.count = count
        self.start_page = start_page
        self.start_index = start_index

        self.end_index = start_index + (count-1)
        if self.end_index > hits:
            self.end_index = hits

class Search(Request):
        
    def __call__(self, query):

        count = query.count
        start_page = query.start_page
        start_index = query.start_index
        
        # return some dummy data
        from random import randint

        status = True
        message = 'Dummy failure'
        hits = randint(0, 100)

        if not status and not hits:
            raise DWSError('The Disovery Web Service failed: %s' % message)

        results = []

        if count < hits:
            c = count
        else:
            c = hits
        for i in xrange(c):
            results.append(('b0de0599-5734-4946-b131-dfc65a16b1de',
                            'Broad Occupational Structure Map of Nepal'))
            
        return SearchResponse(hits, results, count, start_page, start_index)
