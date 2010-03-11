# The medin version string. When changes are made to the application
# this version number should be incremented. It is used in caching to
# ensure the client gets the latest version of a resource.
__version__ = 0.7

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

    return Query(qsl)

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
        super(Search, self).__init__(['%s', 'search.html'])

    def setup(self, environ):
        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)
        
        search_term = q.getSearchTerm(cast=False)
        count = q.getCount()
        sort = q.getSort(cast=False)
        bbox = q.getBBOX()
        start_date = q.getStartDate(cast=False)
        end_date = q.getEndDate(cast=False)
        area = q.getArea()

        tvars=dict(search_term=search_term,
                   count=count,
                   sort=sort,
                   start_date=start_date,
                   end_date=end_date,
                   area=area,
                   bbox=bbox)

        return TemplateContext('Search the MEDIN Data Archive Centres', tvars=tvars)

class Results(MakoApp):

    def __init__(self, path, headers):
        from medin.dws import SearchRequest
        
        self.headers = headers
        self.request = SearchRequest()
        super(Results, self).__init__(path, check_etag=False)

    def setup(self, environ):
        from medin.dws import DWSError
        from copy import copy

        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        try:
            r = self.request(q, environ['logging.logger'])
        except DWSError, e:
            raise HTTPError('%d Discovery Web Service Error' % e.status, e.msg)

        timestamp = r.updated.strftime("%a, %d %b %Y %H:%M:%S GMT")
        etag = check_etag(environ, timestamp)

        results = []
        for id, title, author, abstract, updated, bbox in r.results:
            results.append(dict(id=id,
                                title=title,
                                author=author,
                                abstract=abstract,
                                updated=updated,
                                bbox=bbox))

        start_index = r.start_index
        if start_index < 1:
            start_index = 1

        search_term = r.search_term
        
        tvars=dict(hits=r.hits,
                   query=r.query,
                   search_term = search_term,
                   start_index = start_index,
                   end_index = r.end_index,
                   count = r.count,
                   next_links = r.next_links,
                   prev_links = r.prev_links,
                   last_link = r.last_link,
                   first_link = r.first_link,
                   current_page = r.current_page,
                   page_count = r.page_count,
                   updated = r.updated,
                   results=results)

        title = 'Catalogue page %d of %d' % (r.current_page, r.page_count)
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
        headers = [('Content-type', 'text/html')]
        super(HTMLResults, self).__init__(['%s', 'catalogue.html'], headers)

    def setup(self, environ):
        from copy import deepcopy

        # create the data structure for the template sort logic
        ctxt = super(HTMLResults, self).setup(environ)
        query = deepcopy(ctxt.tvars['query'])

        sorts = {}
        cur_sort, cur_asc = query.getSort(default=('',''))
        for sort in ('title', 'author', 'updated'):
            query.setSort((sort, 1))
            asc = (str(query), (sort == cur_sort and cur_asc == 1))
            query.setSort((sort, 0))
            desc = (str(query), (sort == cur_sort and cur_asc == 0))
            sorts[sort] = dict(asc=asc, desc=desc)
        ctxt.tvars['sort'] = sorts

        return ctxt

class RSSResults(Results):
    def __init__(self):
        headers = [('Content-type', 'application/rss+xml')]
        super(RSSResults, self).__init__(['rss', 'catalogue', '%s.xml'], headers)

class AtomResults(Results):
    def __init__(self):
        headers = [('Content-type', 'application/atom+xml')]
        super(AtomResults, self).__init__(['atom', 'catalogue', '%s.xml'], headers)

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
        from medin.dws import DWSError

        gid = environ['selector.vars']['gid'] # the global metadata identifier

        try:
            r = self.request(gid)
        except DWSError, e:
            raise HTTPError('%d Discovery Web Service Error' % e.status, e.msg)

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
        tvars = dict(gid=r.id,
                     author=r.author,
                     keywords=keywords,
                     metadata=metadata,
                     linkage=linkage,
                     bbox=bbox,
                     topic_category=topic_category,
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

class EnvironProxy:
    """
    Proxy for the environ object providing extra configuration info

    The wrapper provides an interface for accessing portal specific
    directories and resources as well as the standard environ
    interface.
    """

    def __init__(self, environ):
        try:
            root = environ['PORTAL_ROOT']
        except KeyError:
            raise EnvironmentError('The PORTAL_ROOT environment variable is not set')

        import os.path

        if not os.path.isdir(root):
            raise EnvironmentError('The PORTAL_ROOT is not a directory')

        self.root = root.rstrip(os.path.sep)
        
        self.__environ = environ

    def __getattr__(self, name):
        """
        Delegate unhandled attributes to the environment dictionary
        """
        
        return getattr(self.__environ, name)

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
        from medin.dws import DWSError
        import os.path
        import medin.spatial

        gid = environ['selector.vars']['gid'] # the global metadata identifier

        try:
            r = self.request(gid)
        except DWSError, e:
            raise HTTPError('%d Discovery Web Service Error' % e.status, e.msg)

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
        from medin.dws import DWSError
        from os.path import splitext

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        fmt = environ['selector.vars']['format'] # the requested format

        try:
            if fmt not in self.request.getMetadataFormats():
                raise HTTPError('404 Not Found', 'The metadata format is not supported: %s' % fmt)

            r = self.request(gid)
        except DWSError, e:
            raise HTTPError('%d Discovery Web Service Error' % e.status, e.msg)

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

    # provide a choice of templates
    application.add('[/]', GET=TemplateChoice())

    # the OpenSearch Description document
    application.add('/opensearch/catalogue/{template}.xml', GET=OpenSearch())

    # the default entry point for the search
    application.add('/{template}[/]', GET=Search())

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
    application = WSGILog(application, logger)

    # add the Environ configuration middleware
    application = Config(application)

    return application
