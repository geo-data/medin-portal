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
        from medin.dws import DWSError
        
        super(ErrorHandler, self).__init__(*args, **kwargs)

        self.add(HTTPNotModified, self.handleHTTPNotModified)
        self.add(errata.HTTPError, self.handleHTTPError)
        self.add(DWSError, self.handleDWSError)

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

    def handleDWSError(self, exception, environ, start_response):
        if exception.status < 500:
            # it's something we shouldn't propagate as a HTTP error, so set it as a 500
            fmt = '500 Discovery Web Service Error (Code %d)'
        else:
            # it's safe to propagate the error to the client as a HTTP error
            fmt = '%d Discovery Web Service Error'

        e = errata.HTTPError(fmt % exception.status, exception.msg)
        return self.handleHTTPError(e, environ, start_response)

    def handleTemplateLookupException(self, exception, environ, start_response):
        from mako.exceptions import TopLevelLookupException
        import sys

        try:
            exc_info = sys.exc_info()
            message = 'The template could not be found: %s' % str(exception)
            e = errata.HTTPError('404 Not Found', message)
            try:
                return self.handleHTTPError(e, environ, start_response)
                environ['logging.logger'].error('A template could not be found', exc_info=exc_info)
            except TopLevelLookupException:
                # The top level template can't be found, so specify a default
                environ['selector.vars']['template'] = 'light'
                message = 'The template you specified does not exist.'
                e = errata.HTTPError('404 Not Found', message)
                return self.handleHTTPError(e, environ, start_response)
        finally:
            # avoid circular references as per http://docs.python.org/library/sys.html#sys.exc_info
            del exc_info

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

        environ['logging.logger'].exception('The application encountered an unhandled exception')
        
        start_response('500 Internal Server Error', [('Content-type', 'text/plain')])
        return [output]

# The WSGI Applications

class ErrorRenderer(MakoApp):
    def __init__(self, exception):
        self.exception = exception
        content_type = {'full': 'text/html',
                        'light': 'application/xhtml+xml'}
        super(ErrorRenderer, self).__init__(['%s', 'error.html'], check_etag=False, content_type=content_type)

    def setup(self, environ):
        title = 'Error - %s' % self.exception.args[0]
        status = self.exception.args[0]
        tvars = dict(message=self.exception.args[1])
        return TemplateContext(title, status=status, tvars=tvars)

class HTTPErrorRenderer(ErrorRenderer):
    def __init__(self, status, message):
        e = errata.HTTPError(status, message)
        super(HTTPErrorRenderer, self).__init__(e)
