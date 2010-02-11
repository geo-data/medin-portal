# The medin version string. When changes are made to the application
# this version number should be incremented. It is used in caching to
# ensure the client gets the latest version of a resource.
__version__ = 0.4

from errata import HTTPError
from medin.templates import TemplateLookup, MakoApp, TemplateContext

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

        search_term = ' '.join(q.search_term)
        count = q.count
        try:
            sort = ','.join((str(i) for i in q.sort))
        except TypeError:
            sort = None
        bbox = q.bbox

        tvars=dict(search_term=search_term,
                   count=q.count,
                   sort=sort,
                   bbox=bbox)

        return TemplateContext('Search', tvars=tvars)

class Results(MakoApp):

    def __init__(self, path, headers):
        self.headers = headers
        super(Results, self).__init__(path, check_etag=False)

    def setup(self, environ):
        from medin.dws import Search, DWSError
        from copy import copy

        q = get_query(environ)

        try:
            req = Search()
        except DWSError:
            raise HTTPError('500 Internal Server Error', dws.args[0])

        r = req(q)

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

        search_term = ' '.join(r.search_term)

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
        cur_sort, cur_asc = query.sort
        for sort in ('title', 'author', 'updated'):
            query.sort = (sort, 1)
            asc = (str(query), (sort == cur_sort and cur_asc == 1))
            query.sort = (sort, 0)
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
        super(Metadata, self).__init__(path, check_etag=False)

    def setup(self, environ):
        from dws import MetadataRequest

        gid = environ['selector.vars']['gid'] # the global metadata identifier

        try:
            req = MetadataRequest()
        except DWSError:
            raise HTTPError('500 Internal Server Error', dws.args[0])

        r = req(gid)

        # Check if the client needs a new version
        etag = check_etag(environ, r.last_updated())
        headers = [('Etag', etag)]

        return r, headers

class MetadataHTML(Metadata):
    def __init__(self):
        super(MetadataHTML, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        r, headers = super(MetadataHTML, self).setup(environ)

        title = 'Metadata: %s' % r.title
        keywords = r.keywords()
        metadata = r.allElements()
        linkage = r.online_resource()
        bbox = r.bbox()
        tvars = dict(gid=r.id,
                     author=r.author,
                     keywords=keywords,
                     metadata=metadata,
                     linkage=linkage,
                     bbox=bbox,
                     abstract=r.abstract)

        headers.append(('Content-type', 'text/html'))

        return TemplateContext(title, tvars=tvars, headers=headers)

class MetadataKML(Metadata):
    def __init__(self):
        super(MetadataKML, self).__init__(['kml', 'catalogue', 'metadata-%s.kml'])

    def setup(self, environ):
        r, headers = super(MetadataKML, self).setup(environ)

        bbox = r.bbox()
        tvars = dict(gid=r.id,
                     bbox=bbox,
                     author=r.author,
                     abstract=r.abstract)

        headers.append(('Content-type', 'application/vnd.google-earth.kml+xml'))

        return TemplateContext(r.title, tvars=tvars, headers=headers)

def background_raster(template_lookup, environ, doc_root):
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
    from medin.templates import get_script_root

    raster = 'background-wms.xml'
    templatepath = os.path.join('config', raster)
    template = template_lookup.get_template(templatepath)
    rasterpath = os.path.join(doc_root, 'tmp', raster)

    # render the template to the file
    fh = open(rasterpath, 'w')
    ctx = Context(fh, resource_root=get_script_root(environ))
    template.render_context(ctx)
    fh.close()

    _bg_raster = rasterpath
    return rasterpath

def metadata_image(environ, start_response):
    from dws import MetadataRequest
    import os.path
    import medin.spatial

    gid = environ['selector.vars']['gid'] # the global metadata identifier

    try:
        req = MetadataRequest()
    except DWSError:
        raise HTTPError('500 Internal Server Error', dws.args[0])

    try:
        r = req(gid)
    except DWSError:
        raise HTTPError('500 Internal Server Error', dws.args[0]) 

    # Check if the client needs a new version
    etag = check_etag(environ, r.last_updated())

    bbox = r.bbox()
    if not bbox:
        raise HTTPError('404 Not Found', 'The metadata resource does not have a geographic bounding box')

    # get the path the the background raster datasource
    template_lookup = TemplateLookup(environ)
    lookup = template_lookup.lookup()
    rasterfile = background_raster(lookup, environ, template_lookup.doc_root)

    # get the mapfile template
    mappath = os.path.join('config', 'metadata-extent.xml')
    tmpdir = os.path.join(template_lookup.doc_root, 'tmp')
    template = lookup.get_template(mappath)
    mapfile = template.render(background_raster=rasterfile)

    # create the image
    image = medin.spatial.metadata_image(bbox, mapfile)

    # serialise the image
    bytes = image.tostring('png')

    headers = [('Content-Type', 'image/png'),
               ('Etag', etag)]

    start_response('200 OK', headers)
    return [bytes]

def metadata_download(environ, start_response):
    from dws import MetadataRequest
    from os.path import splitext

    gid = environ['selector.vars']['gid'] # the global metadata identifier
    fmt = environ['selector.vars']['format'] # the requested format

    try:
        req = MetadataRequest()
    except DWSError:
        raise HTTPError('500 Internal Server Error', dws.args[0])

    if fmt not in req.getMetadataFormats():
        raise HTTPError('404 Not Found', 'The metadata format is not supported: %s' % fmt)

    try:
        r = req(gid)
    except DWSError:
        raise HTTPError('500 Internal Server Error', dws.args[0]) 

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
