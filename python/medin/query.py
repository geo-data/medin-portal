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

    def __init__(self, qsl, areas, fields, vocabs, max_count=300, *args, **kwargs):
        super(Query, self).__init__(qsl, *args, **kwargs)
        self.raise_errors = False
        self.areas = areas
        self.fields = fields
        self.vocabs = vocabs
        self.max_count = max_count

        # join multiple search terms into a single term
        try:
            self['q'] = ' '.join([t for t in self['q'] if t])
        except KeyError:
            pass

    def clone(self):
        return Query(str(self), self.areas, self.fields, self.max_count)

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
                self.getBoxes()
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

    def addSearchTerm(self, term):
        try:
            self['q'][0] += ' %s' % term
        except KeyError, AttributeError:
            self['q'] = [term]

    def replaceSearchTerm(self, find, replace):
        import re
        pattern = re.compile(r'^("%s"|%s)$' % (find, find), re.IGNORECASE)
        terms = []
        for token in self.getSearchTerm(skip_errors=True):
            token.word = pattern.sub(replace, token.word)
            terms.append(str(token))
        if terms:
            self['q'][0] = ' '.join(terms)

    def getStartDate(self, cast=True, default=''):
        return self.asDate('sd', cast, default, True)

    def getEndDate(self, cast=True, default=''):
        return self.asDate('ed', cast, default, False)

    def asDate(self, key, cast, default, is_start):
        try:
            date = self[key][0].strip()
        except KeyError, AttributeError:
            return default

        import datetime
        
        try:
            dt = datetime.datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            try:
                dt = datetime.datetime.strptime(date, '%Y')
                if not is_start:
                    now = datetime.datetime.now()
                    if dt.year == now.year:
                        # it is this year so set the end date to now
                        dt = now
                    else:
                        dt = dt.replace(month=12, day=31)
            except ValueError:
                try:
                    dt = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    if self.raise_errors:
                        raise QueryError('The following date is not recognised: %s. Please specify the date in the format YYYY-MM-DD' % date)
                    return default

        if self.raise_errors and dt > datetime.datetime.now():
            raise QueryError('The date is in the future: %s' % date)

        if cast: return dt
        return date

    def getBoxes(self, cast=True, default=''):
        try:
            bboxes = self['bbox']
        except KeyError, AttributeError:
            return default

        if not cast:
            return bboxes

        boxes = []
        for bbox in bboxes:
            bbox = bbox.split(',', 3)
            if not len(bbox) == 4:
                if self.raise_errors:
                    raise QueryError('The bounding box must be in the format minx,miny,maxx,maxy')
                return default
            try:
                bbox = [float(n) for n in bbox]
            except ValueError:
                if self.raise_errors:
                    raise QueryError('The bounding box must consist of numbers')
                return default

            if bbox[0] > bbox[2]:
                if self.raise_errors:
                    raise QueryError('The bounding box east value is less than the west')
                return default

            if bbox[1] > bbox[3]:
                if self.raise_errors:
                    raise QueryError('The bounding box north value is less than the south')
                return default

            boxes.append(tuple(bbox))
        return boxes

    def setBoxes(self, bboxes):
        self['bbox'] = [','.join((str(i) for i in box)) for box in bboxes]

    def getDataThemes(self, cast=True, default=''):
        try:
            themes = self['dt']
        except KeyError, AttributeError:
            return default

        if themes[0] == '_all':
            return default

        if not cast:
            return themes

        return self.vocabs.getDataThemesFromIds(themes)

    def setDataThemes(self, themes):
        self['dt'] = self.vocabs.getIdsFromConcepts(themes)

    def getSubThemes(self, cast=True, default=''):
        try:
            themes = self['st']
        except KeyError, AttributeError:
            return default

        if themes[0] == '_all':
            return default

        if not cast:
            return themes

        return self.vocabs.getSubThemesFromIds(themes)

    def setSubThemes(self, themes):
        self['st'] = self.vocabs.getIdsFromConcepts(themes)

    def getParameters(self, cast=True, default=''):
        try:
            parameters = self['p']
        except KeyError, AttributeError:
            return default

        if parameters[0] == '_all':
            return default

        if not cast:
            return parameters

        return self.vocabs.getParametersFromIds(parameters)

    def setParameters(self, parameters):
        self['p'] = self.vocabs.getIdsFromConcepts(parameters)

    def getParameterLabels(self):
        parameters = self.getParameters(cast=False)
        if parameters:
            return [concept.prefLabel for concept in self.vocabs.getParametersFromIds(parameters)]
        sub_themes = self.getSubThemes(cast=False)
        if sub_themes:
            return self.vocabs.getParametersFromSubThemeIds(sub_themes)
        return self.vocabs.getParametersFromDataThemeIds(self.getDataThemes(cast=False))

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
                raise QueryError('The sort parameter must be in the format "field,order"')
            return default

        try:
            asc = int(asc)
            if asc not in (1, 0):
                raise ValueError('Bad sort order value')
        except ValueError:
            if self.raise_errors:
                raise QueryError('The sort order must be either 1 (ascending) or 0 (descending)')
            return default

        if field not in self.fields:
            if self.raise_errors:
                raise QueryError('Unknown sort field: %s. Choose one of: %s' % (field, ', '.join(self.fields)))
            return default

        return field, asc

    def setSort(self, value):
        self['s'] = ','.join((str(i) for i in value))

    def delSort(self):
        del self['s']

    def getCount(self, cast=True, default=20):
        try:
            count = self['c'][0]
        except KeyError, AttributeError:
            return default

        if not cast:
            return count

        try:
            count = int(count)
        except ValueError:
            if self.raise_errors:
                raise QueryError('The number of results to return must be a number')
            return default

        if count > self.max_count:
            if self.raise_errors:
                raise QueryError('The number of results to return cannot be greater than %d' % self.max_count)
            return self.max_count

        return count

    def setCount(self, value):
        self['c'] = value

    def delCount(self):
        del self['c']

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
        def check_area(area):
            if self.raise_errors and len(self['a']) > 1:
                raise QueryError('More than one area is specified: ignoring all areas except for %s' % area)
            return area
        
        try:
            area = self['a'][0]
        except KeyError:
            return default

        if not cast:
            return check_area(area)

        areaname = self.areas.getAreaName(area)
        if areaname:
            return check_area(areaname)

        if self.raise_errors:
            raise QueryError('The area id does not exist: %s' % area)

        return default

    def setArea(self, value):
        self['a'] = value

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
        bboxes = self.getBoxes(default=False)
        a['bbox'] = bboxes
        a['area'] = self.getArea(default=None)

        # add the themes
        a['data_themes'] = self.vocabs.getIdsFromConcepts(self.getDataThemes(default=[]))
        a['sub_themes'] = self.vocabs.getIdsFromConcepts(self.getSubThemes(default=[]))
        a['parameters'] = self.vocabs.getIdsFromConcepts(self.getParameters(default=[]))

        return a

class TargetError(QueryError):
    """
    An error raised when a bad term target is specified
    """
    pass

class TermToken(object):
    """
    A combination of a word, target and query operators

    Multiple TermTokens can be combined to define a query. Query
    operators are `OR` and `-` (NOT).
    """

    def __init__(self, word, target=None, not_=False, or_=False):
        self.word = word
        self.target = target
        self.not_ = not_
        self.or_ = or_

    def __str__(self):
        ret = ''
        if self.or_:
            ret += 'OR '
        if self.not_:
            ret += '-'
        if self.target:
            ret += '%s:' % self.target
        return ret + self.word

    def __repr__(self):
        return "TermToken('%s')" % str(self)

class TermParser(object):
    """
    Parse a search term into a list of tokens

    The returned list contains the <or>, <not>, <target> and <word>
    for each term.
    """

    # The following pattern is designed to parse out the <or>, <not>,
    # <target> and <word> from a user query string. <or> is a the word
    # OR, <not> is a minus sign (-). <target> maps to a search target
    # and <word> is the actual query word.
    #
    # A related pattern which groups <or> and <not> into one operator
    # <op> is:
    # r'(?P<op>(?:\|\s*?-)|[-|])?(?(op)\s*?)(?:(?P<target>[a-zA-Z]+):)?(?P<word>[^\s]+)'
    #
    # See http://docs.python.org/library/re.html for regular
    # expression details.
    pattern = re.compile(r'(?P<or>OR)?(?(or)\s*?)(?P<not>-)?(?(not)\s*?)(?:(?P<targ>[a-zA-Z]+):)?(?P<word>(?:"[^"]+")|(?:[^\s]+))')
    
    targets = set(('', 'a', 'al', 'f', 'l', 'o', 'p', 'rt', 'tc'))
    reserved_words = set(('and', 'or', 'not')) # search terms reserved by the discovery web service

    def __call__(self, querystr, skip_errors=False):
        matches = self.pattern.findall(querystr)

        # Extract all the words and target groups from the query
        # string, creating TermSearch objects from those components.
        tokens = []
        bad_targets = []
        for op_or, op_not, target, word in matches:
            if word.lower() in self.reserved_words:
                continue        # skip reserved words
            if target not in self.targets:
                bad_targets.append(target)
            token = TermToken(word, target, bool(op_not), bool(op_or))
            tokens.append(token)

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

    mapping = {'p': 'parameter',
               'rt': 'resource type',
               'tc': 'topic category',
               'al': 'public access limits',
               'o': 'data originator',
               'f': 'data format'}

    def __call__(self, tokens):
        """
        Returns query tokens transformed into a human friendly structure
        """

        op_map = {False: 'and',
                  True: 'or'}
        query = []
        for i, token in enumerate(tokens):
            op = op_map[token.or_]
            ops = []
            if i and op:
                ops.append(op)
            if token.not_:
                ops.append('not')

            try:
                targets = [token.target, self.mapping[token.target]]
            except KeyError:
                if token.target:
                    targets = [token.target, None]
                else:
                    targets = [None, None]

            if ops:
                op = ' '.join(ops)
            else:
                op = None
                
            term = {'op': op,
                    'target': targets,
                    'word': token.word}
            query.append(term)

        return query
