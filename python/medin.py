# System modules
import os

# Third party modules
import suds                             # for the SOAP client

# private global variables 
_template_dir = None
_template_lookup = None

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

def search(environ, start_response):
    lookup = template_lookup(environ)
    template = lookup.get_template('/ajax/search.html')

    from pprint import pformat
    kwargs = dict(title='Search',
                  request_uri=environ['REQUEST_URI'],
                  environ=pformat(environ))
    
    start_response('200 OK', [('Content-type', 'text/html')])   
    return [template.render(**kwargs)]

def results(environ, start_response):
    lookup = template_lookup(environ)
    template = lookup.get_template('/ajax/results.html')
    
    start_response('200 OK', [('Content-type', 'text/html')])
    return [template.render(title='Results')]

def metadata(environ, start_response):
    gid = environ['selector.vars']['gid'] # the global metadata identifier

    lookup = template_lookup(environ)
    template = lookup.get_template('/ajax/metadata.html')
    
    start_response('200 OK', [('Content-type', 'text/html')])
    return [template.render(title='Metadata %s' % gid, gid=gid)]
