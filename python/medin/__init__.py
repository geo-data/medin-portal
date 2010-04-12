# The medin version string. When changes are made to the application
# this version number should be incremented. It is used in caching to
# ensure the client gets the latest version of a resource.
__version__ = 0.93

from errata import HTTPError

# Custom modules
import medin.error
from medin.templates import TemplateLookup, MakoApp, TemplateContext
from medin.log import msg_info, msg_warn, msg_error

# Third party modules
import selector                        # for URI based dispatch

# Utility functions

def check_etag(environ, etag):
    """Checks whether a client Etag is valid

    If the client etag is valid then a HTTPNotModified exception is
    raised. This exception must be caught and dealt with
    appropriately.

    The argument etag is modified to include application version
    information. This modified etag is returned and should be used as
    the value for the HTTP Etag header."""

    from error import HTTPNotModified

    # format the etag to include the application version
    server_etag = '"%s (v%s)"' % (etag, str(__version__))

    try:
        client_etag = environ['HTTP_IF_NONE_MATCH']
    except KeyError:
        pass
    else:
        if server_etag == client_etag:
            raise HTTPNotModified

    return server_etag

def get_query(environ):
    """Returns an object encapsulating the OpenSearch query parameters"""
    from medin.query import Query

    try:
        qsl = environ['QUERY_STRING']
    except KeyError:
        qsl = ''

    fields = ('updated', 'originator', 'title')
    return Query(qsl, get_areas(environ), fields)

def get_areas(environ):
    """
    Returns the area interface

    Because this object references the thread sensitive sqlite
    database this function returns an object which is unique to the
    calling thread.
    """
    from thread import get_ident

    thread_id = get_ident()
    
    global _areas
    try:
        return _areas[thread_id]
    except NameError:
        _areas = {}
        pass
    except KeyError:
        pass

    from medin.spatial import Areas
    
    areas = _areas[thread_id] = Areas(get_db(environ))
    return areas

def get_db(environ):
    """
    Returns the portal sqlite database object

    The database object is unique to the calling thread to ensure
    thread related problems such as database locking are avoided.
    """
    from thread import get_ident

    thread_id = get_ident()
    global _dbs
    try:
        return _dbs[thread_id]
    except NameError:
        _dbs = {}
        pass
    except KeyError:
        pass

    import os.path, sqlite3
    filepath = os.path.join(environ.root, 'data', 'portal.sqlite')
    
    db = _dbs[thread_id] = sqlite3.connect(filepath)
    return db

# Utility classes

class Proxy:
    """
    Proxy class

    This class wraps an object. It passes all unhandled attribute
    calls to the underlying object. This enables the proxy to override
    the underlying object's attributes. In practice this works like
    runtime inheritance.
    """

    def __init__(self, obj):
        self.__obj = obj

    def __getattr__(self, name):
        """
        Delegate unhandled attributes to the wrapped object
        """
        
        return getattr(self.__obj, name)

# The WSGI Applications

class OpenSearch(MakoApp):
    def __init__(self):
        super(OpenSearch, self).__init__(['opensearch', 'catalogue', '%s.xml'])

    def setup(self, environ):
        title = 'MEDIN Catalogue'
        headers = [('Content-type', 'application/opensearchdescription+xml')]
        return TemplateContext(title, headers=headers)

class Search(MakoApp):
    def __init__(self):
        from medin.dws import SearchRequest
        self.request = SearchRequest()
        super(Search, self).__init__(['%s', 'search.html'])

    def setup(self, environ):
        from medin.dws import RESULT_SIMPLE
        
        areas = get_areas(environ)
        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        # we need to get the number of hits for the query
        count = q.getCount(default=None)
        q.setCount(0)
        r = self.request(q, RESULT_SIMPLE, environ['logging.logger'])
        if count is not None:
            q.setCount(count) # reset the count to it's previous value
        else:
            q.delCount() # delete the count as it wasn't there originally

        search_term = q.getSearchTerm(cast=False)
        sort = q.getSort(cast=False)
        bbox = q.getBBOX()
        start_date = q.getStartDate(cast=False)
        end_date = q.getEndDate(cast=False)
        area = q.getArea(cast=False)
        criteria = q.asDict(False)
        area_type = areas.getAreaType(area)

        area_ids = {'british-isles': areas.britishIsles(),
                    'countries': areas.countries(),
                    'sea-areas': areas.seaAreas(),
                    'progress-areas': areas.chartingProgressAreas(),
                    'ices-rectangles': areas.icesRectangles()}

        tvars=dict(search_term=search_term,
                   hits=r.hits,
                   criteria=criteria,
                   count=count,
                   sort=sort,
                   start_date=start_date,
                   end_date=end_date,
                   area=area,
                   area_type=area_type,
                   area_ids=area_ids,
                   bbox=bbox)

        return TemplateContext('Search the MEDIN Data Archive Centres', tvars=tvars)

class Navigation(object):
    """
    Responsible for creating navigation links
    """

    def __init__(self, hits, query):
        from copy import deepcopy

        self.hits = hits
        self.count = query.getCount()
        self._start_index = query.getStartIndex() - 1 # we use zero based indexing

        # set the index of the final result in this page
        self.end_index = self._start_index + self.count
        if self.end_index > hits:
            self.end_index = hits

        #we make a copy as the query object is modified later
        self._query = deepcopy(query)

    @property
    def start_index(self):
        start_index = self._start_index + 1;
        if start_index < 1:
            start_index = 1
        return start_index

    @property
    def current_page(self):
        try:
            return self._current_page
        except AttributeError:
            pass
        
        from math import ceil

        pages_before = self._start_index / float(self.count)
        self._current_page = int(ceil(pages_before)) + 1

        return self._current_page

    @property
    def page_count(self):
        try:
            return self._page_count
        except AttributeError:
            pass
        
        from math import ceil
        
        pages_before = self._start_index / float(self.count)
        pages_after = (self.hits - self._start_index) / float(self.count)
        self._page_count = int(ceil(pages_before) + ceil(pages_after))

        return self._page_count

    def getNextLinks(self):
        query = self._query
        next_links = []
        next_index = self._start_index + self.count
        ic = 0
        page = self.current_page
        while page < self.page_count and ic < 5:
            page += 1
            ic += 1
            query.setStartIndex(next_index + 1)
            next_links.append({'page': page,
                               'link': str(query)})
            next_index += self.count

        return next_links

    def getLastLink(self):
        query = self._query
        if self.current_page < self.page_count:
            query.setStartIndex(1 + self._start_index + (self.count * (self.page_count - self.current_page)))
            return {'page': self.page_count,
                    'link': str(query)}

        return None

    def getPrevLinks(self):
        query = self._query
        prev_links = []
        prev_index = self._start_index - self.count
        ic = 0
        page = self.current_page
        while page > 1 and ic < 5:
            page -= 1
            ic += 1
            query.setStartIndex(prev_index + 1)
            prev_links.insert(0, {'page': page,
                                  'link': str(query)})
            prev_index -= self.count

        return prev_links

    def getFirstLink(self):
        query = self._query
        if self.current_page > 1:
            query.setStartIndex(1 + self._start_index - (self.count * (self.current_page-1)))
            return {'page': 1,
                    'link': str(query)}

        return None


class Results(MakoApp):

    def __init__(self, path, headers, result_type):
        from medin.dws import SearchRequest
        
        self.headers = headers
        self.result_type = result_type
        self.request = SearchRequest()
        super(Results, self).__init__(path, check_etag=False)

    def setup(self, environ):
        from copy import copy

        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        r = self.request(q, self.result_type, environ['logging.logger'])

        updated = r.lastModified()
        timestamp = updated.strftime("%a, %d %b %Y %H:%M:%S GMT")
        etag = check_etag(environ, timestamp)

        nav = Navigation(r.hits, q)
        search_term = q.getSearchTerm(cast=False)
        tvars=dict(hits=r.hits,
                   query=q,
                   count = q.getCount(),
                   updated = updated,
                   search_term = search_term,
                   start_index = nav.start_index,
                   end_index = nav.end_index,
                   next_links = nav.getNextLinks(),
                   prev_links = nav.getPrevLinks(),
                   last_link = nav.getLastLink(),
                   first_link = nav.getFirstLink(),
                   current_page = nav.current_page,
                   page_count = nav.page_count,
                   results=list(r))

        if r.hits:
            title = 'Catalogue page %d of %d' % (nav.current_page, nav.page_count)
        else:
            title = 'Catalogue results'
        if search_term:
            title += ' for: %s' % search_term

        # modify the headers. We need a local copy of the base headers
        # so we don't alter the instance
        headers = copy(self.headers)

        # propagate the result update time to the HTTP layer
        headers.append(('Etag', etag))

        return TemplateContext(title, tvars=tvars, headers=headers)

class HTMLResults(Results):
    def __init__(self):
        from medin.dws import RESULT_BRIEF
        
        headers = [('Content-type', 'text/html')]
        super(HTMLResults, self).__init__(['%s', 'catalogue.html'], headers, RESULT_BRIEF)

    def setup(self, environ):
        from copy import deepcopy

        # create the data structure for the template sort logic
        ctxt = super(HTMLResults, self).setup(environ)
        query = deepcopy(ctxt.tvars['query'])
        ctxt.tvars['criteria'] = query.asDict(False)

        sorts = {}
        cur_sort, cur_asc = query.getSort(default=('updated', 0))
        for sort in query.fields:
            query.setSort((sort, 1))
            asc = (str(query), (sort == cur_sort and cur_asc == 1))
            query.setSort((sort, 0))
            desc = (str(query), (sort == cur_sort and cur_asc == 0))
            sorts[sort] = dict(asc=asc, desc=desc)
        ctxt.tvars['sort'] = sorts

        return ctxt

class RSSResults(Results):
    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        headers = [('Content-type', 'application/rss+xml')]
        super(RSSResults, self).__init__(['rss', 'catalogue', '%s.xml'], headers, RESULT_SUMMARY)

class AtomResults(Results):
    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        headers = [('Content-type', 'application/atom+xml')]
        super(AtomResults, self).__init__(['atom', 'catalogue', '%s.xml'], headers, RESULT_SUMMARY)

class ResultSummary(object):

    def __init__(self):
        from medin.dws import SearchRequest
        
        self.request = SearchRequest()

    def __call__(self, environ, start_response):
        from medin.dws import RESULT_SIMPLE
        from json import dumps as tojson

        q = get_query(environ)
        q.setCount(0)                   # we don't need any results
        
        r = self.request(q, RESULT_SIMPLE, environ['logging.logger'])

        json = tojson({'status': bool(r),
                       'hits': r.hits,
                       'time': environ['portal.timer'].runtime()})
        
        headers = [('Content-type', 'application/json')]

        start_response('200 OK', headers)
        return [json]
    
class ResultFormat(object):

    def __init__(self, default, formats):
        self.default = default
        self.formats = formats

    def __call__(self, environ, start_response):
        try:
            fmt = environ['selector.vars']['format']
        except KeyError:
            app_class = self.default
        else:
            if fmt is not None:
                try:
                    app_class = self.formats[fmt]
                except KeyError:
                    raise HTTPError('404 Not Found', 'The format is not supported: %s' % fmt)
            else:
                app_class = self.default

        app = app_class()
        return app(environ, start_response)

class Metadata(MakoApp):

    def __init__(self, path):
        from medin.dws import MetadataRequest

        self.request = MetadataRequest()
        super(Metadata, self).__init__(path, check_etag=False)

    def setup(self, environ):

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        r = self.request(gid, areas)

        # Check if the client needs a new version
        headers = []
        if r:
            etag = check_etag(environ, r.last_updated())
            headers.append(('Etag', etag))

        return r, headers

class MetadataHTML(Metadata):
    def __init__(self):
        super(MetadataHTML, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        r, headers = super(MetadataHTML, self).setup(environ)

        if not r:
            raise HTTPError('404 Not Found', 'The metadata resource does not exist')

        title = 'Metadata: %s' % r.title
        keywords = r.keywords()
        metadata = r.allElements()
        linkage = r.online_resource()
        bbox = r.bbox()
        topic_category = r.topicCategory()
        extent = r.extent()
        tvars = dict(gid=r.id,
                     author=r.author,
                     keywords=keywords,
                     metadata=metadata,
                     linkage=linkage,
                     bbox=bbox,
                     topic_category=topic_category,
                     extent=extent,
                     abstract=r.abstract)

        headers.append(('Content-type', 'text/html'))

        return TemplateContext(title, tvars=tvars, headers=headers)

class MetadataKML(Metadata):
    def __init__(self):
        super(MetadataKML, self).__init__(['kml', 'catalogue', 'metadata-%s.kml'])

    def setup(self, environ):
        r, headers = super(MetadataKML, self).setup(environ)

        if r:
            title = r.title
            bbox = r.bbox()
            tvars = dict(gid=r.id,
                         bbox=bbox,
                         author=r.author,
                         abstract=r.abstract)
        else:
            title = ''
            tvars = {}

        headers.append(('Content-type', 'application/vnd.google-earth.kml+xml'))

        return TemplateContext(title, tvars=tvars, headers=headers)

class EnvironProxy(Proxy):
    """
    Proxy for the environ object providing extra configuration info

    The wrapper provides an interface for accessing portal specific
    directories and resources as well as the standard environ
    interface.
    """

    def __init__(self, environ):
        Proxy.__init__(self, environ)
        
        try:
            root = environ['PORTAL_ROOT']
        except KeyError:
            raise EnvironmentError('The PORTAL_ROOT environment variable is not set')

        import os.path

        if not os.path.isdir(root):
            raise EnvironmentError('The PORTAL_ROOT is not a directory')

        self.root = root.rstrip(os.path.sep)
        
    def script_path(self):
        """
        Returns path info after the script name
        """

        path_info = self.get('PATH_INFO', '')
        script_name = self.get('SCRIPT_NAME', '')
        if path_info.startswith(script_name):
            return path_info[len(script_name):]
        return path_info

    # code adapted from http://www.python.org/dev/peps/pep-0333/#url-reconstruction
    def http_uri(self):
        url = self['wsgi.url_scheme']+'://'

        try:
            url += self['HTTP_HOST']
        except KeyError:
            url += self['SERVER_NAME']

            if self['wsgi.url_scheme'] == 'https' and self['SERVER_PORT'] != '443':
                url += ':' + self['SERVER_PORT']
            elif self['SERVER_PORT'] != '80':
                url += ':' + self['SERVER_PORT']

        return url

    def script_uri(self):
        from urllib import quote

        return self.http_uri() + quote(self.get('SCRIPT_NAME',''))

    def resource_uri(self):
        from urllib import quote

        return self.script_uri() + quote(self.get('PATH_INFO',''))

    def request_uri(self):
        if self.get('QUERY_STRING'):
            return self.resource_uri() + '?' + self['QUERY_STRING']
        return self.resource_uri()

class Config(object):
    """
    WSGI middleware that wraps the environment with an Environ instance
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        return self.app(EnvironProxy(environ), start_response)

def background_raster(template_lookup, environ):
    """Return the background raster filepath

    The filepath is to a temporary file, which is created the first
    time this function is called."""

    global _bg_raster
    try:
        return _bg_raster
    except NameError:
        pass

    import os.path
    from mako.runtime import Context

    raster = 'background-wms.xml'
    templatepath = os.path.join('config', raster)
    template = template_lookup.get_template(templatepath)
    rasterpath = os.path.join(environ.root, 'tmp', raster)

    # render the template to the file
    fh = open(rasterpath, 'w')
    ctx = Context(fh, resource_root=environ.script_uri())
    template.render_context(ctx)
    fh.close()

    _bg_raster = rasterpath
    return rasterpath

class MetadataImage(object):
    """
    WSGI app for outputting a metadata image
    """

    def __init__(self):
        from medin.dws import MetadataRequest
        self.request = MetadataRequest()

    def __call__(self, environ, start_response):
        import os.path
        import medin.spatial

        gid = environ['selector.vars']['gid'] # the global metadata identifier

        r = self.request(gid)

        # Check if the client needs a new version
        etag = check_etag(environ, r.last_updated())

        bbox = r.bbox()
        if not bbox:
            raise HTTPError('404 Not Found', 'The metadata resource does not have a geographic bounding box')

        # ensure the background raster datasource has been created
        template_lookup = TemplateLookup(environ)
        lookup = template_lookup.lookup()
        rasterpath = background_raster(lookup, environ)

        # create the mapfile from its template
        mappath = os.path.join('config', 'metadata-extent.xml')
        template = lookup.get_template(mappath)
        mapfile = template.render(root_dir=environ.root)

        # create the image
        image = medin.spatial.metadata_image(bbox, mapfile)

        # serialise the image
        bytes = image.tostring('png')

        headers = [('Content-Type', 'image/png'),
                   ('Etag', etag)]

        start_response('200 OK', headers)
        return [bytes]

class MetadataDownload(object):
    """
    WSGI app for downloading a metadata format
    """

    def __init__(self):
        from medin.dws import MetadataRequest
        self.request = MetadataRequest()

    def __call__(self, environ, start_response):
        from os.path import splitext

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        fmt = environ['selector.vars']['format'] # the requested format

        if fmt not in self.request.getMetadataFormats():
            raise HTTPError('404 Not Found', 'The metadata format is not supported: %s' % fmt)

        r = self.request(gid)

        # Check if the client needs a new version
        etag = check_etag(environ, r.last_updated())

        filename = r.id
        if not splitext(filename)[1]:
            filename += '.xml'

        document = str(r.document)

        headers = [('Content-disposition', 'attachment; filename="%s"' % filename),
                   ('Content-Type', 'application/xml'),
                   ('Etag', etag)]

        start_response('200 OK', headers)
        return [document]

class TemplateChoice(MakoApp):
    def __init__(self):
        super(TemplateChoice, self).__init__(['light', 'templates.html'], False)

    def setup(self, environ):
        return TemplateContext('Choose Your Search Format')

def query_criteria(environ, start_response):
    from json import dumps as tojson
    
    q = get_query(environ)
    
    # Check if the client needs a new version
    etag = check_etag(environ, str(q))

    json = tojson(q.asDict())
    
    headers = [('Content-Type', 'application/json'),
               ('Etag', etag)]
    
    start_response('200 OK', headers)
    return [json]

def get_bbox(environ, start_response):
    from json import dumps as tojson
    from medin.spatial import Areas

    aid = environ['selector.vars']['id'] # the area ID
    
    # Check if the client needs a new version
    etag = check_etag(environ, aid)

    bbox = Areas(get_db(environ)).getBBOX(aid)
    if not bbox:
        raise HTTPError('404 Not Found', 'The area id does not exist: %s' % aid)

    json = tojson(bbox)
    
    headers = [('Content-Type', 'application/json'),
               ('Etag', etag)]
    
    start_response('200 OK', headers)
    return [json] 

class Timer(object):
    """
    Class that performs basic time profiling

    The time in fractional seconds since the class was instantiated
    can be retrieved using the runtime() method.
    """

    def __init__(self):
        from time import time
        self.start = time()

    def runtime(self):
        from time import time
        return time() - self.start

class WSGITimer(object):
    """
    WSGI Middleware that adds a timer to the environ dictionary
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['portal.timer'] = Timer()

        return self.app(environ, start_response)

class Selector(selector.Selector):
    status404 = medin.error.HTTPErrorRenderer('404 Not Found', 'The resource you specified could not be found')

def wsgi_app():
    """
    Return an instance of the Portal's root WSGI application
    """
    
    from medin.spatial import tilecache
    from medin.log import WSGILog

    # Create a WSGI application for URI delegation using Selector
    # (http://lukearno.com/projects/selector/). The order that child
    # applications are added is important; the most specific URL matches
    # must be before the more generic ones.
    application = Selector(consume_path=False)

    # provide the Tile Mapping Service
    application.parser.patterns['tms'] = r'/.*'
    application.add('/spatial/tms[{req:tms}]', _ANY_=tilecache) # for TMS requests to tilecache

    # provide an API to the areas
    application.add('/spatial/areas/{id:word}/extent.json', GET=get_bbox)

    # provide a choice of templates
    application.add('[/]', GET=TemplateChoice())

    # the OpenSearch Description document
    application.add('/opensearch/catalogue/{template}.xml', GET=OpenSearch())

    # the default entry point for the search
    application.add('/{template}[/]', GET=Search())

    # the API for analysing search criteria passed in via GET parameters
    application.add('/{template}/query.json', GET=query_criteria)

    # retrieve the result summary for a query
    application.add('/{template}.json', GET=ResultSummary())

    # create the app to return the required formats
    result_formats = medin.ResultFormat(HTMLResults, {'rss': RSSResults,
                                                      'atom': AtomResults})

    # display and navigate through the result set
    application.add('/{template}/catalogue[.{format:word}]', GET=result_formats)

    # display the metadata
    application.add('/{template}/catalogue/{gid:segment}', GET=MetadataHTML())

    # get the metadata as in KML format
    application.add('/{template}/catalogue/{gid:segment}/kml', GET=MetadataKML())

    # get an image representing the metadata bounds.
    application.add('/{template}/catalogue/{gid:segment}/extent.png', GET=MetadataImage())

    # download the metadata
    application.add('/{template}/catalogue/{gid:segment}/{format:segment}', GET=MetadataDownload())

    # add our Error handler
    application = medin.error.ErrorHandler(application)

    # add the logging handlers
    import logging
    logger = logging.getLogger('medin')

    #from logging.handlers import SMTPHandler
    #smtp_handler = SMTPHandler(('localhost', 1025),
    #                           'hrz@geodata.soton.ac.uk',
    #                           'hrz@geodata.soton.ac.uk',
    #                           'MEDIN Portal Error')
    #smtp_handler.setLevel(logging.ERROR)
    #logger.addHandler(smtp_handler)
    logger.setLevel(logging.DEBUG)
    #scl = logging.getLogger('suds.client')
    #scl.setLevel(logging.DEBUG)
    #scl.addHandler(logging.StreamHandler())
    application = WSGILog(application, logger)

    # add the Environ configuration middleware
    application = Config(application)

    # start the timer
    application = WSGITimer(application)

    return application
