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

# The medin version string. When changes are made to the application
# this version number should be incremented. It is used in caching to
# ensure the client gets the latest version of a resource.
__version__ = 1.7

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

class EnvironNormalise(object):
    """
    WSGI Middleware that normalises the environment

    Currently this responds to user-agent strings and adapts the HTTP
    ACCEPT header.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        """
        Add text/html to the Internet Explorer ACCEPT header

        This is necessary as it isn't specified explicitly and
        therefore the application otherwise returns
        application/xhtml+xml by default for the light template.
        """
        try:
            ua = environ['HTTP_USER_AGENT']
        except KeyError:
            pass
        else:
            if 'text/html' not in ua and 'MSIE' in ua:
                try:
                    environ['HTTP_ACCEPT'] = 'text/html,' + environ['HTTP_ACCEPT']
                except KeyError:
                    pass
            
        return self.app(environ, start_response)

class TemplateChooser(object):
    """
    WSGI Middleware associating content-types with a template
    """
    def __init__(self, default_template):
        self.templates = {}
        self.default_template = default_template

    def addContentTypes(self, app, template, content_types, default=None):
        """
        Associate a WSGI app and a template with one or more content-types
        """
        try:
            mediator = self.templates[template].app
        except KeyError:
            from mediator import Mediator
            # create a Mediator inside a normalised environment
            mediator = Mediator()
            self.templates[template] = EnvironNormalise(mediator)

        # Add the specified content types, wrapping them in middleware
        # that adds the content-type header.
        for content_type in content_types:
            wrapp = self.contentWrapper(app, content_type+';charset=utf-8')
            mediator.add(content_type, wrapp)

        # Add the default content type
        if default:
            wrapp = self.contentWrapper(app, default+';charset=utf-8')
            mediator.add('*/*', wrapp)

    def contentWrapper(self, app, content_type):
        """
        Wrap an app with middleware that outputs a specific content-type header

        This appends the specified content-type to the headers of the
        WSGI app passed in as an argument.
        """
        # the WSGI middleware that injects the content-type
        def wrapper(environ, start_response):
            # the content-type is added in the start_response
            def wrapped_response(status, headers):
                headers.append(('Content-Type', content_type))
                start_response(status, headers)

            # add the content type to the environment
            environ['portal.content-type'] = content_type

            return app(environ, wrapped_response)

        return wrapper

    def __call__(self, environ, start_response):
        """
        Call an app associated with a template
        """
        from medin.templates import get_template_name

        template = get_template_name(environ)
        if template is None:
            template = self.default_template

        if not self.templates:
            raise RuntimeError('No template applications have been added')
        
        try:
            app = self.templates[template]
        except KeyError:
            from medin.templates import set_template_name
            # set the template name so this error can't become
            # recursive which is the case if this code is used in an
            # error handler
            if self.default_template in self.templates:
                # use the default template
                set_template_name(environ, self.default_template)
            else:
                # use any template
                set_template_name(environ, self.templates.keys()[0])
            raise HTTPError('404 Not Found', 'The requested template does not exist')

        return app(environ, start_response)

def http404(environ, start_response):
    """
    Raises a HTTP 404 Not Found exception when called

    The actual exception should be handled elsewhere.
    """
    msg = 'The resource you specified could not be found: %s' % environ.request_uri()
    raise HTTPError('404 Not Found', msg)

def wsgi_app():
    """
    Return an instance of the Portal's root WSGI application
    """
    from medin import views
    from medin.spatial import tilecache
    from medin.log import WSGILog, ExcludeUserMessageFilter, MakoFormatter

    # create the WSGI configuration middleware
    config = WSGIWrapper(Config, 'app', name='portal.ini')

    # specify the html content types returned by the template
    # apps. Ideally 'application/xhtml+xml' would be output by all
    # templates. However Internet Explorer does not recognise it and
    # Firefox complains about the document.write() javascript call
    # when it is specified for the full template. A specific default
    # is specified for the light template so that it validates with
    # the W3C validator.
    light_types = ['text/html', 'application/xhtml+xml']
    light_default = 'application/xhtml+xml'
    full_types = ['text/html']
    default_template = 'light'
    
    # Create a WSGI application for URI delegation using Selector
    # (http://lukearno.com/projects/selector/). The order that child
    # applications are added is important; the most specific URL matches
    # must be before the more generic ones.
    application = selector.Selector(consume_path=False)

    # replace the default 404 handler on the selector
    application.status404 = http404

    # provide the proxying service for AJAX requests
    #application.add('/proxy', GET=proxy) Not currently used

    # provide the Tile Mapping Service
    application.parser.patterns['tms'] = r'/.*'
    application.add('/spatial/tms[{req:tms}]', _ANY_=tilecache) # for TMS requests to tilecache

    # provide an API to the areas
    application.add('/spatial/areas/{id:word}/extent.json', GET=views.get_bbox)

    # provide a choice of HTML interfaces between light and full
    app = TemplateChooser(default_template)
    view = views.TemplateChoice()
    app.addContentTypes(view, 'light', light_types, light_default)
    application.add('[/]', GET=app)

    # the OpenSearch Description document
    application.add('/opensearch/catalogue/{template}.xml', GET=views.OpenSearch())

    # the default entry point for the search
    app = TemplateChooser(default_template)
    view = views.Search()
    app.addContentTypes(view, 'light', light_types, light_default)
    app.addContentTypes(view, 'full', full_types)
    application.add('/{template}[/]',
                    GET=app,
                    POST=config(views.Comment(app)))

    # the API for analysing search criteria passed in via GET parameters
    application.add('/{template}/query.json', GET=views.query_criteria)

    # retrieve the result summary for a query
    application.add('/{template}.json', GET=views.ResultSummary())

    # create the app to return the required formats
    app = TemplateChooser(default_template)
    view = views.HTMLResults()
    app.addContentTypes(view, 'light', light_types, light_default)
    app.addContentTypes(view, 'full', full_types)
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
    app = TemplateChooser(default_template)
    view = views.MetadataHTML()
    app.addContentTypes(view, 'light', light_types, light_default)
    app.addContentTypes(view, 'full', full_types)
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

    # Add our Error handler
    # create a callable to render the error
    def error_renderer(exception, environ, start_response):
        app = TemplateChooser(default_template)
        view = views.ErrorRenderer(exception)
        app.addContentTypes(view, 'light', light_types, light_default)
        app.addContentTypes(view, 'full', full_types)
        return app(environ, start_response)
    
    application = medin.error.ErrorHandler(application, error_renderer)

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

    # set up the handler for the standard error stream
    error_log = logging.StreamHandler()
    error_log.setLevel(logging.DEBUG)
    error_log.addFilter(ExcludeUserMessageFilter()) # we don't want user messages being logged
    formatter = MakoFormatter("%(request_uri)s at %(asctime)s:\n%(message)s")
    error_log.setFormatter(formatter)
    logger.addHandler(error_log)

    #scl = logging.getLogger('suds.client')
    #scl.setLevel(logging.DEBUG)
    #scl.addHandler(logging.StreamHandler())
    application = WSGILog(application, logger)

    # add the Environ configuration middleware
    application = Environ(application)

    # start the timer
    application = WSGITimer(application)

    return application
