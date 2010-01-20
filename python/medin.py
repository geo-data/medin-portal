# System modules
import os

# Third party modules
import suds                             # for the SOAP client
import errata                           # for the error handling

# Helper Functions

def parse_qsl(environ):
    try:
        qsl = environ['QUERY_STRING']
    except KeyError:
        return []
    
    import cgi
    return cgi.parse_qsl(qsl)

# Utility Classes

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
        def template_lookup(environ):
            try:
                return MakoApp._template_lookup
            except AttributeError:
                pass

            def get_template_dir(environ):
                try:
                    return MakoApp._template_dir
                except AttributeError:
                    pass

                try:
                    doc_root = environ['DOCUMENT_ROOT']
                except KeyError:
                    raise EnvironmentError('The DOCUMENT_ROOT environment variable is not available')

                template_dir = os.path.join(os.path.dirname(doc_root), 'templates')
                if not os.path.exists(template_dir):
                    raise RuntimeError('The template directory does not exist: %s' % template_dir)

                MakoApp._template_dir = template_dir
                return template_dir

            from mako.lookup import TemplateLookup

            template_dir = get_template_dir(environ)
            _template_lookup = TemplateLookup(directories=[template_dir],
                                              input_encoding='utf-8',
                                              output_encoding='utf-8',
                                              filesystem_checks=False)

            MakoApp._template_lookup = _template_lookup
            return _template_lookup
        
        lookup = template_lookup(environ)
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

        from pprint import pformat

        kwargs.update(dict(title=title,
                           request_uri=environ['REQUEST_URI'],
                           http_root=get_http_root(environ),
                           script_root=get_script_root(environ),
                           environ=pformat(environ)))
        return kwargs

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

# The error handler
class ErrorHandler(errata.ErrorHandler):
    """WSGI post-processor for handling errors using Mako templates.

    Exception instances of (or derived from) HTTPError are caught and
    the appropriate response is returned to the client."""

    def __init__(self, *args, **kwargs):
        super(ErrorHandler, self).__init__(*args, **kwargs)

        self.add(errata.HTTPError, self.handleHTTPError)

        from mako.exceptions import TopLevelLookupException
        self.add(TopLevelLookupException, self.handleMakoError)

    def handleHTTPError(self, exception, environ, start_response):
        """Handler for HTTPErrors"""

        renderer = ErrorRenderer(exception)
        return renderer(environ, start_response)

    def handleMakoError(self, exception, environ, start_response):
        from mako.exceptions import TopLevelLookupException
        
        message = 'The template could not be found: %s' % str(exception)
        e = errata.HTTPError('404 Not Found', message)
        try:
            return self.handleHTTPError(e, environ, start_response)
        except TopLevelLookupException:
            # The top level template can't be found, so specify a default
            environ['selector.vars']['template'] = 'light'
            message = 'The template you specified does not exist.'
            e = errata.HTTPError('404 Not Found', message)
            return self.handleHTTPError(e, environ, start_response)

# The WSGI Applications

class ErrorRenderer(MakoApp):
    def __init__(self, exception):
        self.exception = exception
        super(ErrorRenderer, self).__init__(['%s', 'error.html'])

    def setup(self, environ):
        title = 'Error - %s' % self.exception.args[0]
        status = self.exception.args[0]
        tvars = dict(message=self.exception.args[1])
        return TemplateContext(title, status=status, tvars=tvars)

class HTTPErrorRenderer(ErrorRenderer):
    def __init__(self, status, message):
        e = errata.HTTPError(status, message)
        super(HTTPErrorRenderer, self).__init__(e)

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
    def __init__(self):
        super(Results, self).__init__(['%s', 'catalogue.html'])

    def setup(self, environ):
        return TemplateContext('Results')

class Metadata(MakoApp):
    def __init__(self):
        super(Metadata, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        title = 'Metadata %s' % gid
        tvars = dict(gid=gid)

        return TemplateContext(title, tvars=tvars)

class TemplateChoice(MakoApp):
    def __init__(self):
        super(TemplateChoice, self).__init__(['light', 'templates.html'], False)

    def setup(self, environ):
        return TemplateContext('Choose Your Search Format')
