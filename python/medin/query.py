class GETParams(object):
    """Stores HTTP GET query parameters"""

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

class Query(GETParams):
    """Provides an interface to MEDIN OpenSearch query parameters"""

    @property
    def search_term(self):
        try:
            return self['q']
        except KeyError:
            return []

    @property
    def bbox(self):
        try:
            return self['bbox'][0].split(',', 3)
        except KeyError, AttributeError:
            return []

    @bbox.setter
    def bbox(self, box):
        self['bbox'] = ','.join((str(i) for i in box))

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
