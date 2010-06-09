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
