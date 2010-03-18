import re

class QueryError(ValueError):
    pass

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
                p = str(p)
                if len(p):
                    params.append('%s=%s' % (k, quote_plus(p)))

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

    def __init__(self, qsl, areas, *args, **kwargs):
        super(Query, self).__init__(qsl, *args, **kwargs)
        self.raise_errors = False
        self.areas = areas

    def verify(self):
        """
        Check the validity of the Query, logging any errors
        """

        errors = []
        errsetting = self.raise_errors
        self.raise_errors = True
            
        try:
            try:
                tokens = self.getSearchTerm()
            except QueryError, e:
                errors.append(str(e))
            
            try:
                start_date = self.getStartDate()
            except QueryError, e:
                errors.append('There is a problem with the start date. %s' % str(e))
                start_date = None

            try:
                end_date = self.getEndDate()
            except QueryError, e:
                errors.append('There is a problem with the end date. %s' % str(e))
                end_date = None

            if start_date and end_date and start_date > end_date:
                errors.append('The start date cannot be greater than the end date')

            try:
                self.getBBOX()
            except QueryError, e:
                errors.append(str(e))

            try:
                self.getSort()
            except QueryError, e:
                errors.append(str(e))

            try:
                self.getCount()
            except QueryError, e:
                errors.append(str(e))

            try:
                self.getStartIndex()
            except QueryError, e:
                errors.append(str(e))

            try:
                self.getArea()
            except QueryError, e:
                errors.append(str(e))
                
        finally:
            self.raise_errors = errsetting
            
        return errors

    def getSearchTerm(self, cast=True, default='', skip_errors=False):
        try:
            qstring = self['q'][0]
            if cast:
                return TermParser()(qstring, skip_errors)
            return qstring
        except KeyError:
            pass
        except QueryError:
            if self.raise_errors: raise

        return default

    def getStartDate(self, cast=True, default=''):
        return self.asDate('sd', cast, default)

    def getEndDate(self, cast=True, default=''):
        return self.asDate('ed', cast, default)

    def asDate(self, key, cast, default):
        try:
            date = self[key][0]
        except KeyError, AttributeError:
            return default

        import datetime
        try:
            dt = datetime.datetime.strptime(date, '%Y-%m-%d')
            if cast:
                return dt
            return date
        except ValueError:
            try:
                dt = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')
                if cast:
                    return dt
                return date
            except ValueError:
                if self.raise_errors:
                    raise QueryError('The following date is not recognised: %s. Please specify the date in the format YYYY-MM-DD' % date)

        return default

    def getBBOX(self, cast=True, default=''):
        try:
            bbox = self['bbox'][0]
        except KeyError, AttributeError:
            return default

        if not cast:
            return bbox

        bbox = bbox.split(',', 3)
        if not len(bbox) == 4:
            raise QueryError('The bounding box must be in the format minx,miny,maxx,maxy')
        return bbox

    def setBBOX(self, bbox):
        self['bbox'] = ','.join((str(i) for i in box))

    def getSort(self, cast=True, default=''):
        try:
            sort = self['s'][0]
        except KeyError, AttributeError:
            return default

        if not cast:
            return sort
        
        try:
            field, asc = sort.split(',', 1)
        except ValueError:
            if self.raise_errors:
                raise QueryError('The sort parameter must be in the format field,order')
            return default

        try:
            asc = int(asc)
        except ValueError:
            if self.raise_errors:
                raise QueryError('The order must be an integer')
            return default

        return field, asc

    def setSort(self, value):
        self['s'] = ','.join((str(i) for i in value))

    def getCount(self, cast=True, default=20):
        try:
            count = self['c'][0]
        except KeyError, AttributeError:
            return default

        if not cast:
            return count

        try:
            return int(count)
        except ValueError:
            if self.raise_errors:
                raise QueryError('The number of results to return must be a number')

        return default

    def setCount(self, value):
        self['c'] = value

    def getStartIndex(self, cast=True, default=1):
        try:
            idx = self['i'][0]
        except KeyError:
            return default

        if not cast:
            return idx

        try:
            return int(idx)
        except ValueError:
            if self.raise_errors:
                raise QueryError('The result starting index must be a number')

        return default

    def setStartIndex(self, value):
        self['i'] = value

    def getArea(self, cast=True, default=''):
        try:
            area = self['a'][0]
        except KeyError:
            return default

        if not cast:
            return area

        areaname = self.areas.getAreaName(area)
        if areaname:
            return areaname

        if self.raise_errors:
            raise QueryError('The area id does not exist: %s' % area)

        return default

    def asDict(self, verify=True):
        """
        Return the query as a dictionary structure
        """

        # add any errors
        a = {}
        if verify:
            a['errors'] = self.verify()

        # add the terms
        analyser = TermAnalyser()
        tokens = self.getSearchTerm(skip_errors=True)
        a['terms'] = analyser(tokens)

        # add the dates
        dates = {}
        start = self.getStartDate(cast=False, default=None)
        end = self.getEndDate(cast=False, default=None)
        if start:
            dates['start'] = start
        if end:
            dates['end'] = end
        a['dates'] = dates

        # add the area
        bbox = self.getBBOX(cast=False, default=False)
        if bbox: bbox = True
        a['bbox'] = bbox
        a['area'] = self.getArea(default=None)

        return a

class TargetError(QueryError):
    """
    An error raised when a bad term target is specified
    """
    pass

class TermParser(object):
    """
    Parse a search term into a list of tokens

    The returned list contains the <or>, <not>, <target> and <word>
    for each term.
    """

    # The following pattern is designed to parse out the <or>, <not>,
    # <target> and <word> from a user query string. <or> is a pipe
    # (|), <not> is a minus sign (-). <target> maps to a search target
    # and <word> is the actual query word.
    #
    # A related pattern which groups <or> and <not> into one operator
    # <op> is:
    # r'(?P<op>(?:\|\s*?-)|[-|])?(?(op)\s*?)(?:(?P<target>[a-zA-Z]+):)?(?P<word>[^\s]+)'
    #
    # See http://docs.python.org/library/re.html for regular
    # expression details.
    pattern = re.compile(r'(?P<or>[|])?(?(or)\s*?)(?P<not>-)?(?(not)\s*?)(?:(?P<targ>[a-zA-Z]+):)?(?P<word>[^\s]+)')
    
    targets = set(('', 'a', 'al', 'f', 'l', 'o', 'p', 'rt', 'tc'))

    def __call__(self, querystr, skip_errors=False):
        matches = self.pattern.findall(querystr)

        # Extract all the words and target groups from the query
        # string, creating TermSearch objects from those components.
        tokens = []
        bad_targets = []
        for op_or, op_not, target, word in matches:
            if target not in self.targets:
                bad_targets.append(target)
            tokens.append((op_or, op_not, target, word))

        if not skip_errors and bad_targets:
            targets = [t for t in self.targets if t]
            targets.sort()
            targets = ', '.join(targets)

            if len(bad_targets) == 1:
                msg = 'The following target in the search term is not recognised: %s' % bad_targets[0]
            else:
                msg = 'The following targets in the search term are not recognised: %s' % ', '.join(bad_targets)
            raise TargetError('%s. Please choose one of: %s' % (msg, targets))

            
        return tokens

class TermAnalyser(object):

    mapping = {'a': 'author',
               'p': 'parameter',
               'rt': 'resource type',
               'tc': 'topic category',
               'l': 'lineage',
               'al': 'public access limits',
               'o': 'data originator',
               'f': 'data format'}

    def __call__(self, tokens):
        """
        Returns query tokens transformed into a human friendly structure
        """

        op_map = {'': 'and',
                  '|': 'or'}
        query = []
        for i, (op_or, op_not, target, word) in enumerate(tokens):
            op = op_map[op_or]
            ops = []
            if i and op:
                ops.append(op)
            if op_not:
                ops.append('not')

            try:
                targets = [target, self.mapping[target]]
            except KeyError:
                if target:
                    targets = [target, None]
                else:
                    targets = [None, None]

            if ops:
                op = ' '.join(ops)
            else:
                op = None
                
            term = {'op': op,
                    'target': targets,
                    'word': word}
            query.append(term)

        return query
