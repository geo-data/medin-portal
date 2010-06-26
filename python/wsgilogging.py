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

"""
Logging for WSGI

This module provides logging for WSGI applications based on the
standard Python logging module.

The primary object is WSGILog, instances of which are WSGI middleware
applications. Example usage is:

import logging
from wsgiref.simple_server import demo_app, make_server

logger = logging.getLogger('demo')
application = WSGILog(demo_app, logger)
httpd = make_server('', 8008, application)
httpd.serve_once()

WSGILog is instantiated with a WSGI application and a standard
logging.Logger instance. When called by a WSGI framework WSGILog adds
the keys 'logging.logger' and 'logging.handler' to the environ
dictionary, enabling setting and retrieval of log records by WSGI
applications:

environ['logging.logger'].info('Some information')
environ['logging.handler'].records()    # list of LogRecord objects

LogRecords are filtered so that only those records produced by the
current request are available from 'logging.handler'.
"""

import logging

class Handler(logging.Handler):
    
    def __init__(self):
        logging.Handler.__init__(self)
        self.flush()
    
    def flush(self):
        """
        Clear all records
        """

        self._records = []
        self._levels = {}

    def close(self):
        del self._records
        del self._levels
        logging.Handler.close(self)

    def emit(self, record):
        self._records.append(record)
        idx = len(self._records)-1
        try:
            self._levels[record.levelname].append(idx)
        except KeyError:
            self._levels[record.levelname] = [idx]
    
    def records(self, levels=None):
        if not levels:
            return self._records

        records = []
        for levelname in levels:
            try:
                records.extend((self._records[i] for i in self._levels[levelname]))
            except KeyError:
                # it's a logging level that doesn't have any records
                pass

        return records

class LoggerAdapter(logging.LoggerAdapter):

    def __init__(self, environ, logger, extras):
        logging.LoggerAdapter.__init__(self, logger, extras)
        self.environ = environ

        # the cache of loggers that have been created
        self._loggers = {self.logger.name: self}

    def getLogger(self, name):
        """
        Return a LoggerAdapter with the same instance 'extra' arguments

        This should be called by code that wants a logger object with
        the same extra parameters as the current LoggerAdapter
        instance e.g.

        parent_logger = LoggerAdapter(logging.getLogger('parent'), {'key': 'value'})
        child_logger = parent_logger.getLogger('parent.child')

        child_logger will now produce LogRecords that have a key
        attribute with the value 'value'
        """

        try:
            return self._loggers[name]
        except KeyError:
            pass

        logger = self.__class__(logging.getLogger(name), self.extra)

        # add the new logger to the cache...
        self._loggers.update(logger._loggers)
        # and add the cache to the new logger
        logger._loggers = self._loggers

class Filter(logging.Filter):

    def __init__(self, id, *args, **kwargs):
        logging.Filter.__init__(self, *args, **kwargs)
        self.id = id

    def filter(self, record):
        """
        Only allow records that have the same id as the filter
        """
        
        try:
            return record.id == self.id
        except AttributeError:
            return False

class WSGILog(object):

    def __init__(self, app, logger):
        self.app = app
        self.logger = logger

    def getId(self, environ):
        """
        Create an unique ID for this request
        """

        if 'UNIQUE_ID' in environ:
            return environ['UNIQUE_ID']

        id_ = environ.get('REMOTE_PORT', '')
        id_ += ':' + environ.get('REMOTE_ADDR', '')
        id_ += environ.get('SCRIPT_NAME','')
        id_ += environ.get('PATH_INFO','')
        if 'QUERY_STRING' in environ:
            return id_ + '?' + environ['QUERY_STRING']
        return id_

    def getHandler(self, environ):
        return Handler()

    def getLogger(self, environ, logger, extras):
        return LoggerAdapter(environ, logger, extras)

    def __call__(self, environ, start_response):
        from wsgiref.util import request_uri

        environ['logging.handler'] = hdlr = self.getHandler(environ)
        hdlr.setLevel(logging.DEBUG)

        id_ = self.getId(environ)
        hdlr.addFilter(Filter(id_, self.logger.name))
        environ['logging.logger'] = self.getLogger(environ, self.logger, dict(id=id_,
                                                                              request_uri=request_uri(environ)))

        self.logger.addHandler(hdlr)
        try:
            return self.app(environ, start_response)
        finally:
            # Always ensure the handler is removed as it is request specific
            self.logger.removeHandler(hdlr)
