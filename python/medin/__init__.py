# The medin version string. When changes are made to the application
# this version number should be incremented. It is used in caching to
# ensure the client gets the latest version of a resource.
__version__ = 0.97

from errata import HTTPError           # for HTTP exceptions
import medin.error

# Third party modules
import selector                        # for URI based dispatch

# Utility classes

class Proxy:
    """
    Proxy class

    This class wraps an object. It passes all unhandled attribute
    calls to the underlying object. This enables the proxy to override
    the underlying object's attributes. In practice this works like
    runtime inheritance.
    """

    def __init__(self, obj):
        self.__obj = obj

    def __getattr__(self, name):
        """
        Delegate unhandled attributes to the wrapped object
        """
        
        return getattr(self.__obj, name)

# WSGI Middleware Applications

class WSGIWrapper(object):
    """
    Wrap a WSGI application with an instance of a specified class

    This is a factory class that acts as a callable and wraps a WSGI
    application with a specific class instance. This saves having to
    supply the construction arguments multiple times to the same class.
    """

    def __init__(self, class_name, param_name, **kwargs):
        self.class_name = class_name
        self.param_name = param_name
        self.kwargs = kwargs

    def __call__(self, app):
        kwargs = self.kwargs.copy()
        kwargs[self.param_name] = app
        return self.class_name(**kwargs)

class EnvironProxy(Proxy):
    """
    Proxy for the environ object providing extra configuration info

    The wrapper provides an interface for accessing portal specific
    directories and resources as well as the standard environ
    interface.
    """

    def __init__(self, environ):
        Proxy.__init__(self, environ)
        
        try:
            root = environ['PORTAL_ROOT']
        except KeyError:
            raise EnvironmentError('The PORTAL_ROOT environment variable is not set')

        import os.path

        if not os.path.isdir(root):
            raise EnvironmentError('The PORTAL_ROOT is not a directory')

        self.root = root.rstrip(os.path.sep)
        
    def script_path(self):
        """
        Returns path info after the script name
        """

        path_info = self.get('PATH_INFO', '')
        script_name = self.get('SCRIPT_NAME', '')
        if path_info.startswith(script_name):
            return path_info[len(script_name):]
        return path_info

    # code adapted from http://www.python.org/dev/peps/pep-0333/#url-reconstruction
    def http_uri(self):
        url = self['wsgi.url_scheme']+'://'

        try:
            url += self['HTTP_HOST']
        except KeyError:
            url += self['SERVER_NAME']

            if self['wsgi.url_scheme'] == 'https' and self['SERVER_PORT'] != '443':
                url += ':' + self['SERVER_PORT']
            elif self['SERVER_PORT'] != '80':
                url += ':' + self['SERVER_PORT']

        return url

    def script_uri(self):
        from urllib import quote

        return self.http_uri() + quote(self.get('SCRIPT_NAME',''))

    def resource_uri(self):
        from urllib import quote

        return self.script_uri() + quote(self.get('PATH_INFO',''))

    def request_uri(self):
        if self.get('QUERY_STRING'):
            return self.resource_uri() + '?' + self['QUERY_STRING']
        return self.resource_uri()

class Environ(object):
    """
    WSGI middleware that wraps the environment with an EnvironProxy instance
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        return self.app(EnvironProxy(environ), start_response)

class Timer(object):
    """
    Class that performs basic time profiling

    The time in fractional seconds since the class was instantiated
    can be retrieved using the runtime() method.
    """

    def __init__(self):
        from time import time
        self.start = time()

    def runtime(self):
        from time import time
        return time() - self.start

class WSGITimer(object):
    """
    WSGI Middleware that adds a timer to the environ dictionary
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['portal.timer'] = Timer()

        return self.app(environ, start_response)

class Config(object):
    """
    WSGI middleware used to configure an application

    This adds a key to the environ dictionary called config that has a
    ConfigParser instance as its value. This instance is created from
    an INI file whose name is specified in the constructor. This file
    must reside in the etc directory of the application root
    directory.
    """

    def __init__(self, app, name):
        self.app = app
        self.name = name
        self.config = None
    
    def getConfig(self, environ):
        if self.config:
            return self.config

        import os.path
        from ConfigParser import SafeConfigParser
        
        ini_file = os.path.join(environ.root, 'etc', self.name)
        try:
            fp = open(ini_file, 'r')
        except Exception, e:
            raise HTTPError('500 Configuration Error', 'the INI file could not be read: %s' % str(e))

        try:
            self.config = config = SafeConfigParser()
            config.readfp(fp)
        finally:
            fp.close()

        return config

    def __call__(self, environ, start_response):
        environ['config'] = self.getConfig(environ)
        
        # delegate to the wrapped app
        return self.app(environ, start_response)

class Selector(selector.Selector):
    status404 = medin.error.HTTPErrorRenderer('404 Not Found', 'The resource you specified could not be found')

def wsgi_app():
    """
    Return an instance of the Portal's root WSGI application
    """
    from medin import views
    from medin.spatial import tilecache
    from medin.log import WSGILog

    # create the WSGI configuration middleware
    config = WSGIWrapper(Config, 'app', name='portal.ini')

    # Create a WSGI application for URI delegation using Selector
    # (http://lukearno.com/projects/selector/). The order that child
    # applications are added is important; the most specific URL matches
    # must be before the more generic ones.
    application = Selector(consume_path=False)

    # provide the proxying service for AJAX requests
    #application.add('/proxy', GET=proxy) Not currently used

    # provide the Tile Mapping Service
    application.parser.patterns['tms'] = r'/.*'
    application.add('/spatial/tms[{req:tms}]', _ANY_=tilecache) # for TMS requests to tilecache

    # provide an API to the areas
    application.add('/spatial/areas/{id:word}/extent.json', GET=views.get_bbox)

    # provide a choice of templates
    application.add('[/]', GET=views.TemplateChoice())

    # the OpenSearch Description document
    application.add('/opensearch/catalogue/{template}.xml', GET=views.OpenSearch())

    # the default entry point for the search
    app = views.Search()
    application.add('/{template}[/]',
                    GET=app,
                    POST=config(views.Comment(app)))

    # the API for analysing search criteria passed in via GET parameters
    application.add('/{template}/query.json', GET=views.query_criteria)

    # retrieve the result summary for a query
    application.add('/{template}.json', GET=views.ResultSummary())

    # create the app to return the required formats
    app = views.HTMLResults()
    result_formats = views.ResultFormat(app, {'rss': views.RSSResults(),
                                              'atom': views.AtomResults()})

    # search by country
    application.add('/{template}/areas/{area:segment}/{name:segment}',
                    GET=views.AreaResults(result_formats),
                    POST=config(views.Comment(views.AreaResults(app))))

    # display and navigate through the result set
    application.add('/{template}/catalogue[.{format:word}]',
                    GET=result_formats,
                    POST=config(views.Comment(app)))

    # display the metadata
    app = views.MetadataHTML()
    application.add('/{template}/catalogue/{gid:segment}',
                    GET=app,
                    POST=config(views.Comment(app)))

    # get the metadata as in KML format
    application.add('/{template}/catalogue/{gid:segment}/kml', GET=views.MetadataKML())

    # get an image representing the metadata bounds.
    application.add('/{template}/catalogue/{gid:segment}/extent.png', GET=views.MetadataImage())

    # download the metadata as CSV
    application.add('/{template}/catalogue/{gid:segment}/csv', GET=views.MetadataCSV())

    # download the metadata as XML
    application.add('/{template}/catalogue/{gid:segment}/{format:segment}', GET=views.MetadataXML())

    # add our Error handler
    application = medin.error.ErrorHandler(application)

    # add the logging handlers
    import logging
    logger = logging.getLogger('medin')

    #from logging.handlers import SMTPHandler
    #smtp_handler = SMTPHandler(('localhost', 1025),
    #                           'hrz@geodata.soton.ac.uk',
    #                           'hrz@geodata.soton.ac.uk',
    #                           'MEDIN Portal Error')
    #smtp_handler.setLevel(logging.ERROR)
    #logger.addHandler(smtp_handler)
    logger.setLevel(logging.DEBUG)
    #scl = logging.getLogger('suds.client')
    #scl.setLevel(logging.DEBUG)
    #scl.addHandler(logging.StreamHandler())
    application = WSGILog(application, logger)

    # add the Environ configuration middleware
    application = Environ(application)

    # start the timer
    application = WSGITimer(application)

    return application
