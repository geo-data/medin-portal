from medin.templates import MakoApp, TemplateContext
import errata                           # for the error handling

# Specialised exception classes
class HTTPNotModified(errata.HTTPError):
    def __init__(self):
        super(HTTPNotModified, self).__init__('304 Not Modified', '')

# The error handler
class ErrorHandler(errata.ErrorHandler):
    """WSGI post-processor for handling errors using Mako templates.

    Exception instances of (or derived from) HTTPError are caught and
    the appropriate response is returned to the client."""

    def __init__(self, *args, **kwargs):
        super(ErrorHandler, self).__init__(*args, **kwargs)

        self.add(HTTPNotModified, self.handleHTTPNotModified)
        self.add(errata.HTTPError, self.handleHTTPError)

        from mako.exceptions import TopLevelLookupException
        self.add(TopLevelLookupException, self.handleTemplateLookupException)
        self.add(Exception, self.handleException)

    def handleHTTPNotModified(self, exception, environ, start_response):
        """Handler for HTTPNotModified exceptions"""

        start_response('304 Not Modified', [])
        return []

    def handleHTTPError(self, exception, environ, start_response):
        """Handler for HTTPErrors"""

        renderer = ErrorRenderer(exception)
        return renderer(environ, start_response)

    def handleTemplateLookupException(self, exception, environ, start_response):
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

    def handleException(self, exception, environ, start_response):
        from mako.exceptions import RichTraceback
        from cStringIO import StringIO
        
        traceback = RichTraceback()
        buf = StringIO()
        
        for (filename, lineno, function, line) in traceback.traceback:
            buf.write("File %s, line %s, in %s\n" % (filename, lineno, function))
            buf.write(str(line))
            buf.write("\n")
        buf.write("%s: %s\n" % (str(traceback.error.__class__.__name__), traceback.error))
        output = buf.getvalue()
        
        start_response('500 Internal Server Error', [('Content-type', 'text/plain')])
        return [output]

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
