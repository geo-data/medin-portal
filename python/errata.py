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

FORMAT_NONE = 0
FORMAT_TRACEBACK = 1
FORMAT_EXCEPTION = 2
FORMAT_MESSAGE = 3

class ErrorHandler(object):
    """WSGI post-processer aimed at handling all exceptions.

    All exceptions are caught and returned as 500 Internal Server
    Error to the browser. The output format for both the client and
    the log can be chosen by passing the appropriate FORMAT_*
    constants during instantiation. The format can be customised by
    overriding the format* methods.

    Handlers for specific error types can be added using the add()
    method. Handlers should act as WSGI applications; they have the
    following signature:

      handleException(exception, environ, start_response)

    where exception is the exception instance being handled.
    """

    def __init__(self, app, log_format=FORMAT_TRACEBACK, output_format=FORMAT_MESSAGE):
        self.app = app
        self.log_format = log_format
        self.output_format = output_format
        self.handlers = {Exception: self.handleException}

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""

        try:
            return self.app(environ, start_response)
        except Exception, e:
            handler = self.getHandler(e)
            return handler(e, environ, start_response)

    def add(self, exception_class, handler):
        self.handlers[exception_class] = handler

    def getHandler(self, exception):
        try:
            return self.handlers[exception.__class__]
        except KeyError:
            # get the exceptions and sort them into an inheritance hierarchy
            exceptions = self.handlers.keys()
            exceptions.sort()

            # find a handler for the exception (should default to Exception)
            for eclass in exceptions:
                if isinstance(exception, eclass):
                    return self.handlers[eclass]

        # a catch-all that shouldn't be reached
        return self.handleException

    def handleException(self, exception, environ, start_response):
        """Handle an Exception of any kind"""
        
        formats = [None, self.formatTraceback, self.formatException, self.formatMessage]

        # get a format for the log
        try:
            logFormat = formats[self.log_format]
        except:
            raise ValueError('Bad log format choice')

        # Get a format for the output
        try:
            outputFormat = formats[self.output_format]
        except:
            raise ValueError('Bad output format choice')

        # write to the log
        if logFormat is not None:
            environ['wsgi.errors'].write(logFormat(exception))

        # create the output
        if outputFormat is not None:
            output = outputFormat(exception)
        else:
            output = ''

        # get response headers
        response_headers = self.responseHeaders()

        # write to the client
        start_response('500 Internal Server Error', response_headers)
        return [output]

    def responseHeaders(self):
        """Return the response headers to send to start_response()"""
        
        return [('Content-type', 'text/plain')]

    def formatTraceback(self, e):
        """Format an exception as a traceback"""
        
        import traceback
        return traceback.format_exc()

    def formatException(self, e):
        """Format an exception to show it's type and content"""
        
        import traceback
        return ''.join(traceback.format_exception_only(e.__class__, e))

    def formatMessage(self, e):
        """Format an exception to only show it's content"""
        return "%s\n" % str(e)

class HTTPError(Exception):
    """An exception representing an HTTP error.

    This exception carries a payload indicating the response status,
    the message itself, and any headers."""

    def __init__(self, status, message, headers = [('Content-type', 'text/plain')]):
        Exception.__init__(self, status, message, headers)

    def __str__(self):
        return self.args[1]

class HTTPErrorHandler(ErrorHandler):
    """WSGI post-processor aimed at handling HTTP errors.

    Exception instances of (or derived from) HTTPError are caught and
    the appropriate response is returned to the client."""

    def __init__(self, *args, **kwargs):
        super(HTTPErrorHandler, self).__init__(*args, **kwargs)
        self.add(HTTPError, self.handleHTTPError)

    def handleHTTPError(self, exception, environ, start_response):
        """Handler for HTTPErrors"""

        start_response(exception.args[0], exception.args[2])
        return [exception.args[1]]
