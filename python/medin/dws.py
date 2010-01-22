import os

# Third party modules
import suds                             # for the SOAP client

class Query(object):
    """Stores OpenSearch query parameters"""

    def __init__(self, qsl=''):
        import cgi

        self.params = {}
        for k, v in cgi.parse_qsl(qsl):
            self[k] = v

    def __getitem__(self, k):
        return self.params[k]

    def __setitem__(self, k, v):
        try:
            self.params[k].append(v)
        except KeyError:
            self.params[k] = [v]

    def __str__(self):
        from urllib import quote_plus
        params = []
        for k, v in self.params.items():
            for p in v:
                params.append('%s=%s' % (k, quote_plus(p)))

        return '&'.join(params)

class Request(object):

    def __init__(self, wsdl=None):
        if wsdl is None:     
            wsdl = 'file://%s' % os.path.join(os.path.dirname(__file__), 'data', 'dws.wsdl')

        self.client = suds.client.Client(wsdl)

    def __call__(query):
        raise NotImplementedError('The query must be overridden in a subclass')

class Search(Request):
        
    def __call__(self, query):
        for i in xrange(43):
            document_id = 'b0de0599-5734-4946-b131-dfc65a16b1de'
            title = 'Broad Occupational Structure Map of Nepal'
            
            yield document_id, title
