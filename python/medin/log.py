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

import wsgilogging
import logging

# Add a default log handler for the portal to prevent log warnings
# (http://docs.python.org/library/logging.html#configuring-logging-for-a-library)
class NullHandler(logging.Handler):
    def emit(self, record):
        pass

h = NullHandler()
logging.getLogger("medin").addHandler(h)

# Custom error levels. These all fall under the general logging.INFO
# error level
USER_INFO = 21
USER_WARNING = 22
USER_ERROR = 23

# Add the custom levels to the logging module
logging.addLevelName(USER_INFO, 'USER_INFO')
logging.addLevelName(USER_WARNING, 'USER_WARNING')
logging.addLevelName(USER_ERROR, 'USER_ERROR')

# Utility functions for logging user messages

def msg_info(environ, msg, *args, **kwargs):
    environ['logging.logger'].userInfo(msg, *args, **kwargs)

def msg_warn(environ, msg, *args, **kwargs):
    environ['logging.logger'].userWarning(msg, *args, **kwargs)

def msg_error(environ, msg, *args, **kwargs):
    environ['logging.logger'].userError(msg, *args, **kwargs)

class LoggerAdapter(wsgilogging.LoggerAdapter):
    """
    A LoggerAdapter that adds methods for custom user messages
    """

    def userInfo(self, msg, *args, **kwargs):
        return self.log(USER_INFO, msg, *args, **kwargs)

    def userWarning(self, msg, *args, **kwargs):
        return self.log(USER_WARNING, msg, *args, **kwargs)

    def userError(self, msg, *args, **kwargs):
        return self.log(USER_ERROR, msg, *args, **kwargs)

class Handler(wsgilogging.Handler):
    """
    A handler that provides easy access to info, warning and error logs
    """

    def notices(self):
        return self.records(('USER_INFO',))

    def warnings(self):
        return self.records(('USER_WARNING',))

    def errors(self):
        return self.records(('USER_ERROR',))

class WSGILog(wsgilogging.WSGILog):
    """
    A WSGILog that uses a custom LoggerAdapter
    """

    def getLogger(self, environ, logger, extras):
         return LoggerAdapter(logger, extras)

    def getHandler(self, environ):
        return Handler()

class LevelExcludeFilter(logging.Filter):
    """
    Filter that excludes records with from specific logging levels
    """
    def __init__(self, levels, *args, **kwargs):
        logging.Filter.__init__(self, *args, **kwargs)
        self.levels = levels            # level numbers to exclude

    def filter(self, record):
        return record.levelno not in self.levels

class ExcludeUserMessageFilter(LevelExcludeFilter):
    """
    Filter that excludes user messages
    """
    def __init__(self, *args, **kwargs):
        levels = [USER_INFO, USER_WARNING, USER_ERROR]
        LevelExcludeFilter.__init__(self, levels, *args, **kwargs)
