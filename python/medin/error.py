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
        # log the exception
        environ['logging.logger'].exception('The application encountered an unhandled exception')

        # change the exception to a HTTPError and delegate
        exception = errata.HTTPError('500 Portal Error', 'Sorry - the portal has encountered a critical problem. The error has been logged and will be dealt with as soon as possible.')
        return self.handleHTTPError(exception, environ, start_response)

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
