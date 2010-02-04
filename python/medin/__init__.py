# System modules
import os

from errata import HTTPError

# Utility Classes

class TemplateLookup(object):

    def __init__(self, environ):
        try:
            self.template_dir = self.__class__._template_dir
            self.doc_root = self.__class__._doc_root
            return
        except AttributeError:
            pass

        try:
            doc_root = environ['DOCUMENT_ROOT']
        except KeyError:
            raise EnvironmentError('The DOCUMENT_ROOT environment variable is not available')

        self.doc_root = self.__class__._doc_root = os.path.dirname(doc_root)
        self.template_dir = self.__class__._template_dir = os.path.join(self.doc_root, 'templates')
        if not os.path.exists(self.template_dir):
            raise RuntimeError('The template directory does not exist: %s' % self.template_dir)

    def lookup(self):
        try:
            return self.__class_._template_lookup
        except AttributeError:
            pass

        from mako.lookup import TemplateLookup

        module_dir = os.path.join(self.doc_root, 'tmp')
        self.__class__._template_lookup = TemplateLookup(directories=[self.template_dir],
                                                         input_encoding='utf-8',
                                                         output_encoding='utf-8',
                                                         filesystem_checks=False,
                                                         module_directory=module_dir)
        return self.__class__._template_lookup
    
class MakoApp(object):
    """Base class creating WSGI application for rendering Mako templates"""

    def __init__(self, path, expand=True):
        self.path = path
        self.expand = expand

    def setup(self, environ):
        return TemplateContext('')

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""
        
        template = self.get_template(environ, self.path, self.expand)

        ctxt = self.setup(environ)
        
        kwargs = self.get_template_vars(environ, ctxt.title)
        kwargs.update(ctxt.tvars)
    
        output = template.render(**kwargs)

        start_response(ctxt.status, ctxt.headers)
        return [output]

    def get_template(self, environ, path, expand=True):
        template_lookup = TemplateLookup(environ)
        lookup = template_lookup.lookup()
        path = os.path.join(os.path.sep, *path)
        if expand:
            try:
                template = environ['selector.vars']['template'] # the template
            except KeyError:
                try:
                    # try and get the template as the first path entry
                    template = environ['PATH_INFO'].split('/')[1]
                except KeyError, IndexError:
                    raise RuntimeError('No template is specified')
                
            path = path % template
        return lookup.get_template(path)

    def get_template_vars(self, environ, title, **kwargs):
        def get_http_root(environ):
            return '%s://%s' % (environ['wsgi.url_scheme'], environ['HTTP_HOST'])

        def get_script_root(environ):
            return ''.join((get_http_root(environ), environ['SCRIPT_NAME']))

        def get_resource_root(environ):
            try:
                return get_script_root(environ) + environ['PATH_INFO']
            except KeyError:
                 return get_script_root(environ)
        
        vars = dict(title=title,
                    request_uri=environ['REQUEST_URI'],
                    http_root=get_http_root(environ),
                    script_root=get_script_root(environ),
                    resource_root=get_resource_root(environ),
                    environ=environ)

        # Add some useful environment variables to the template
        for k in ('REQUEST_URI', 'QUERY_STRING'):
            kl = k.lower()
            try:
                vars[kl] = environ[k]
            except KeyError:
                vars[kl] = environ['']

        if vars['query_string']: vars['query_string'] = '?' +  vars['query_string']

        # combine the kwargs and vars, overriding vars keys with
        # kwargs if present
        vars.update(kwargs)
        return vars

class TemplateContext(object):
    def __init__(self, title, headers=None, tvars=None, status='200 OK'):
        self.status = status
        if headers is None:
            headers = [('Content-type', 'text/html')]
        self.headers = headers
        self.title = title
        if tvars is None:
            tvars = {}
        self.tvars = tvars

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
        return TemplateContext('Search')

class Results(MakoApp):

    def __init__(self, path, headers):
        self.headers = headers
        super(Results, self).__init__(path)

    def setup(self, environ):
        from medin.dws import SearchQuery, Search, DWSError

        try:
            qsl = environ['QUERY_STRING']
        except KeyError:
            qsl = ''

        q = SearchQuery(qsl)
        try:
            req = Search()
        except DWSError:
            raise HTTPError('500 Internal Server Error', dws.args[0])

        r = req(q)
        results = []
        for id, title, originator, updated in r.results:
            results.append(dict(id=id,
                                title=title,
                                originator=originator,
                                updated=updated))

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

        if search_term:
            title = 'Catalogue: %s' % search_term
        else:
            title = 'Catalogue'

        # propagate the result update time to the HTTP layer
        self.headers.append(('Last-Modified', r.updated.strftime("%a, %d %b %Y %H:%M:%S GMT")))

        return TemplateContext(title, tvars=tvars, headers=self.headers)

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
        for sort in ('title', 'originator', 'updated'):
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
    def __init__(self):
        super(Metadata, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        from dws import MetadataRequest

        gid = environ['selector.vars']['gid'] # the global metadata identifier

        try:
            req = MetadataRequest()
        except DWSError:
            raise HTTPError('500 Internal Server Error', dws.args[0])

        r = req(gid)

        title = 'Metadata: %s' % r.title
        keywords = r.keywords()
        metadata = r.allElements()
        linkage = r.online_resource()
        bbox = r.bbox()
        tvars = dict(gid=r.id,
                     keywords=keywords,
                     metadata=metadata,
                     linkage=linkage,
                     bbox=bbox,
                     abstract=r.abstract)

        return TemplateContext(title, tvars=tvars)

def metadata_image(environ, start_response):
    from dws import MetadataRequest
    import os.path
    from json import dumps as tojson
    import mapnik

    gid = environ['selector.vars']['gid'] # the global metadata identifier

    try:
        req = MetadataRequest()
    except DWSError:
        raise HTTPError('500 Internal Server Error', dws.args[0])

    try:
        r = req(gid)
    except DWSError:
        raise HTTPError('500 Internal Server Error', dws.args[0]) 

    try:
        minx, miny, maxx, maxy = r.bbox()
    except ValueError:
        raise HTTPError('404 Not Found', 'The metadata resource does not have a geographic bounding box')

    # create the bounding box as a json string
    bbox = dict(type='Polygon',
                coordinates=[[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]])
    json = tojson(bbox)

    # get the mapfile template
    template_lookup = TemplateLookup(environ)
    lookup = template_lookup.lookup()
    mappath = os.path.join('config', 'metadata-extent.xml')
    data_dir = os.path.join(template_lookup.doc_root, 'data')
    template = lookup.get_template(mappath)
    mapfile = template.render(data_dir=data_dir)

    # instantiate the map
    m = mapnik.Map(250, 250)
    mapnik.load_map_from_string(m, mapfile)

    # set the datasource for the last layer to show the bounding box
    datasource = mapnik.Ogr(file=json, layer='OGRGeoJSON')
    m.layers[-1].datasource = datasource

    # create an image of the area of interest with a border
    border = 35.0                       # percentage border
    dx = (maxx - minx) * (border / 100)
    minx -= dx; maxx += dx
    dy = (maxy - miny) * (border / 100)
    miny -= dy; maxy += dy
    bbox = mapnik.Envelope(mapnik.Coord(minx, miny), mapnik.Coord(maxx, maxy))
    m.zoom_to_box(bbox)
    image = mapnik.Image(m.width, m.height)
    mapnik.render(m, image)
    
    # serialise the image
    bytes = image.tostring('png')

    headers = [('Content-Type', 'image/png')]

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

    filename = r.id
    if not splitext(filename)[1]:
        filename += '.xml'

    document = str(r.document)
        
    headers = [('Content-disposition', 'attachment; filename="%s"' % filename),
               ('Content-Type', 'application/xml')]

    start_response('200 OK', headers)
    return [document]

class TemplateChoice(MakoApp):
    def __init__(self):
        super(TemplateChoice, self).__init__(['light', 'templates.html'], False)

    def setup(self, environ):
        return TemplateContext('Choose Your Search Format')
