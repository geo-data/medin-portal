# System modules
import os

# Third party modules
import suds                             # for the SOAP client

# private global variables 
_template_dir = None
_template_lookup = None


# Helper Functions

def parse_qsl(environ):
    try:
        qsl = environ['QUERY_STRING']
    except KeyError:
        return []
    
    import cgi
    return cgi.parse_qsl(qsl)

def get_template_dir(environ):
    global _template_dir
    if _template_dir is not None:
        return _template_dir
    
    try:
        doc_root = environ['DOCUMENT_ROOT']
    except KeyError:
        raise EnvironmentError('The DOCUMENT_ROOT environment variable is not available')

    template_dir = os.path.join(os.path.dirname(doc_root), 'templates')
    if not os.path.exists(template_dir):
        raise RuntimeError('The template directory does not exist: %s' % template_dir)

    _template_dir = template_dir
    return _template_dir
    
def template_lookup(environ):
    global _template_lookup
    if _template_lookup is not None:
        return _template_lookup
    
    from mako.lookup import TemplateLookup

    template_dir = get_template_dir(environ)
    _template_lookup = TemplateLookup(directories=[template_dir], filesystem_checks=False)

    return _template_lookup

def get_template(environ, path, expand=True):
    lookup = template_lookup(environ)
    path = os.path.join(os.path.sep, *path)
    if expand:
        try:
            template = environ['selector.vars']['template'] # the template
        except KeyError:
            raise RuntimeError('No template is specified')
        path = path % template
    return lookup.get_template(path)

def get_template_kwargs(environ, title, **kwargs):
    from pprint import pformat
    
    kwargs.update(dict(title=title,
                       request_uri=environ['REQUEST_URI'],
                       http_root=get_http_root(environ),
                       script_root=get_script_root(environ),
                       environ=pformat(environ)))
    return kwargs

def get_http_root(environ):
    return '%s://%s' % (environ['wsgi.url_scheme'], environ['HTTP_HOST'])

def get_script_root(environ):
    return ''.join((get_http_root(environ), environ['SCRIPT_NAME']))

# The WSGI Applications

def opensearch(environ, start_response):
    template = get_template(environ, ['opensearch', 'catalogue', '%s.xml'])
    kwargs = get_template_kwargs(environ, 'MEDIN Catalogue')
    
    start_response('200 OK', [('Content-type', 'application/opensearchdescription+xml')])   
    return [template.render(**kwargs)]

def search(environ, start_response):
    template = get_template(environ, ['%s', 'search.html'])
    kwargs = get_template_kwargs(environ, 'Search')
    
    start_response('200 OK', [('Content-type', 'text/html')])   
    return [template.render(**kwargs)]

def results(environ, start_response):
    template = get_template(environ, ['%s', 'catalogue.html'])
    kwargs = get_template_kwargs(environ, 'Results')

    start_response('200 OK', [('Content-type', 'text/html')])
    return [template.render(**kwargs)]

def metadata(environ, start_response):
    gid = environ['selector.vars']['gid'] # the global metadata identifier

    template = get_template(environ, ['%s', 'metadata.html'])
    kwargs = get_template_kwargs(environ, 'Metadata %s' % gid,
                                 gid=gid)
    
    start_response('200 OK', [('Content-type', 'text/html')])
    return [template.render(**kwargs)]

def template(environ, start_response):
    template = get_template(environ, ['light', 'templates.html'], False)
    kwargs = get_template_kwargs(environ, 'Choose Your Search Format')
    
    start_response('200 OK', [('Content-type', 'text/html')])
    return [template.render(**kwargs)]
