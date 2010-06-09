# The medin version string. When changes are made to the application
# this version number should be incremented. It is used in caching to
# ensure the client gets the latest version of a resource.
__version__ = 0.96

from errata import HTTPError

# Custom modules
import medin.error
from medin.templates import TemplateLookup, MakoApp, TemplateContext
from medin.log import msg_info, msg_warn, msg_error

# Third party modules
import selector                        # for URI based dispatch

# Utility functions

def check_etag(environ, etag):
    """Checks whether a client Etag is valid

    If the client etag is valid then a HTTPNotModified exception is
    raised. This exception must be caught and dealt with
    appropriately.

    The argument etag is modified to include application version
    information. This modified etag is returned and should be used as
    the value for the HTTP Etag header."""

    from error import HTTPNotModified

    # format the etag to include the application version
    server_etag = '"%s (v%s)"' % (etag, str(__version__))

    try:
        client_etag = environ['HTTP_IF_NONE_MATCH']
    except KeyError:
        pass
    else:
        if server_etag == client_etag:
            raise HTTPNotModified

    return server_etag

def set_query(query, environ):
    environ['QUERY_STRING'] = str(query)

def get_query(environ):
    """Returns an object encapsulating the OpenSearch query parameters"""
    from medin.query import Query

    try:
        qsl = environ['QUERY_STRING']
    except KeyError:
        qsl = ''

    fields = ('updated', 'originator', 'title')
    return Query(qsl, get_areas(environ), fields)

def get_areas(environ):
    """
    Returns the area interface

    Because this object references the thread sensitive sqlite
    database this function returns an object which is unique to the
    calling thread.
    """
    from thread import get_ident

    thread_id = get_ident()
    
    global _areas
    try:
        return _areas[thread_id]
    except NameError:
        _areas = {}
        pass
    except KeyError:
        pass

    from medin.spatial import Areas
    
    areas = _areas[thread_id] = Areas(get_db(environ))
    return areas

def get_db(environ):
    """
    Returns the portal sqlite database object

    The database object is unique to the calling thread to ensure
    thread related problems such as database locking are avoided.
    """
    from thread import get_ident

    thread_id = get_ident()
    global _dbs
    try:
        return _dbs[thread_id]
    except NameError:
        _dbs = {}
        pass
    except KeyError:
        pass

    import os.path, sqlite3
    filepath = os.path.join(environ.root, 'data', 'portal.sqlite')
    
    db = _dbs[thread_id] = sqlite3.connect(filepath)
    return db

def get_post(environ):
    """
    Return the contents of a POST as a cgi.FieldStorage instance
    """
    from cgi import FieldStorage
    
    fp = environ['wsgi.input']
    return FieldStorage(fp, environ=environ)

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

# The WSGI Applications

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

class Comment(object):
    """
    WSGI middleware application for processing user comments
    """

    def __init__(self, app):
        self.app = app

    def sendComment(self, from_addr, to_addr, subject, comment, server, port):
        """
        Email a comment

        See
        http://docs.python.org/library/email-examples.html#email-examples
        for email examples.
        """
        # Import smtplib for the actual sending function
        import smtplib

        # Import the email modules we'll need
        from email.mime.text import MIMEText

        # Create a text/plain message
        msg = MIMEText(comment)
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addr

        # Send the message via our own SMTP server, but don't include the
        # envelope header.
        s = smtplib.SMTP(server, port)
        s.sendmail(from_addr, [to_addr], msg.as_string())
        s.quit()

    def __call__(self, environ, start_response):
        form = get_post(environ)
        comment = form.getfirst('comment')
        check = form.getfirst('comment-check')
        request_uri = environ.request_uri()

        if check:
            # try and catch any spam bots as they usually fill in hidden fields
            msg_warn(environ, 'The comment failed the spam filter and was not submitted')
        if environ['HTTP_REFERER'] != request_uri:
            msg_error(environ, 'The comment must be submitted from the appropriate page')
        if not comment:
            msg_warn(environ, 'You did not fill in the comment field')
        else:
            from ConfigParser import NoOptionError
            
            email = form.getfirst('comment-email')
            title = form.getfirst('comment-title', 'Unknown page')
            name = form.getfirst('comment-name', 'an anonymous user')
            ip = environ['REMOTE_ADDR']
            subject = 'Comment on ' + title
            
            msg = "The following comment was sent by %s (IP address %s) using the page at %s\n" % (name, ip, request_uri)
            if email:
                msg += "This user's email address is <%s> (you can contact them by replying to this message).\n\n" % email
            else:
                msg += "This user did not provide an email address.\n\n"
            msg += comment

            # get required variables from the configuration
            config = environ['config']
            to_addr = config.get('DEFAULT', 'email')
            try:
                server = config.get('SMTP', 'server')
            except NoOptionError:
                server = None
            try:
                port = config.get('SMTP', 'port')
            except NoOptionError:
                port = None

            if not email: from_addr = '"MEDIN Portal Comment" <%s>' % to_addr
            else: from_addr = email

            # email the comment
            self.sendComment(from_addr, to_addr, subject, msg, server, port)
            msg_info(environ, 'Thank you for your comment')
        
        # delegate to the wrapped app
        return self.app(environ, start_response)

class OpenSearch(MakoApp):
    def __init__(self):
        super(OpenSearch, self).__init__(['opensearch', 'catalogue', '%s.xml'])

    def setup(self, environ):
        title = 'MEDIN Catalogue'
        headers = [('Content-type', 'application/opensearchdescription+xml')]
        return TemplateContext(title, headers=headers)

class Search(MakoApp):
    def __init__(self):
        from medin.dws import SearchRequest
        self.request = SearchRequest()
        super(Search, self).__init__(['%s', 'search.html'])

    def setup(self, environ):
        from medin.dws import RESULT_SIMPLE
        
        areas = get_areas(environ)
        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        # we need to get the number of hits for the query
        count = q.getCount(default=None)
        q.setCount(0)
        r = self.request(q, RESULT_SIMPLE, environ['logging.logger'])
        if count is not None:
            q.setCount(count) # reset the count to it's previous value
        else:
            q.delCount() # delete the count as it wasn't there originally

        search_term = q.getSearchTerm(cast=False)
        sort = q.getSort(cast=False)
        bbox = q.getBBOX()
        start_date = q.getStartDate(cast=False)
        end_date = q.getEndDate(cast=False)
        area = q.getArea(cast=False)
        criteria = q.asDict(False)
        area_type = areas.getAreaType(area)

        area_ids = {'british-isles': areas.britishIsles(),
                    'countries': areas.countries(),
                    'sea-areas': areas.seaAreas(),
                    'progress-areas': areas.chartingProgressAreas(),
                    'ices-rectangles': areas.icesRectangles()}

        tvars=dict(search_term=search_term,
                   hits=r.hits,
                   criteria=criteria,
                   count=count,
                   sort=sort,
                   start_date=start_date,
                   end_date=end_date,
                   area=area,
                   area_type=area_type,
                   area_ids=area_ids,
                   bbox=bbox)

        return TemplateContext('Search the MEDIN Data Archive Centres', tvars=tvars)

class Navigation(object):
    """
    Responsible for creating navigation links
    """

    def __init__(self, hits, query):
        from copy import deepcopy

        self.hits = hits
        self.count = query.getCount()
        self._start_index = query.getStartIndex() - 1 # we use zero based indexing

        # set the index of the final result in this page
        self.end_index = self._start_index + self.count
        if self.end_index > hits:
            self.end_index = hits

        #we make a copy as the query object is modified later
        self._query = deepcopy(query)

    @property
    def start_index(self):
        start_index = self._start_index + 1;
        if start_index < 1:
            start_index = 1
        return start_index

    @property
    def current_page(self):
        try:
            return self._current_page
        except AttributeError:
            pass
        
        from math import ceil

        pages_before = self._start_index / float(self.count)
        self._current_page = int(ceil(pages_before)) + 1

        return self._current_page

    @property
    def page_count(self):
        try:
            return self._page_count
        except AttributeError:
            pass
        
        from math import ceil
        
        pages_before = self._start_index / float(self.count)
        pages_after = (self.hits - self._start_index) / float(self.count)
        self._page_count = int(ceil(pages_before) + ceil(pages_after))

        return self._page_count

    def getNextLinks(self):
        query = self._query
        next_links = []
        next_index = self._start_index + self.count
        ic = 0
        page = self.current_page
        while page < self.page_count and ic < 5:
            page += 1
            ic += 1
            query.setStartIndex(next_index + 1)
            next_links.append({'page': page,
                               'link': str(query)})
            next_index += self.count

        return next_links

    def getLastLink(self):
        query = self._query
        if self.current_page < self.page_count:
            query.setStartIndex(1 + self._start_index + (self.count * (self.page_count - self.current_page)))
            return {'page': self.page_count,
                    'link': str(query)}

        return None

    def getPrevLinks(self):
        query = self._query
        prev_links = []
        prev_index = self._start_index - self.count
        ic = 0
        page = self.current_page
        while page > 1 and ic < 5:
            page -= 1
            ic += 1
            query.setStartIndex(prev_index + 1)
            prev_links.insert(0, {'page': page,
                                  'link': str(query)})
            prev_index -= self.count

        return prev_links

    def getFirstLink(self):
        query = self._query
        if self.current_page > 1:
            query.setStartIndex(1 + self._start_index - (self.count * (self.current_page-1)))
            return {'page': 1,
                    'link': str(query)}

        return None


class Results(MakoApp):

    def __init__(self, path, headers, result_type):
        from medin.dws import SearchRequest
        
        self.headers = headers
        self.result_type = result_type
        self.request = SearchRequest()
        super(Results, self).__init__(path, check_etag=False)

    def setup(self, environ):
        from copy import copy

        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        r = self.request(q, self.result_type, environ['logging.logger'])

        updated = r.lastModified()
        timestamp = updated.strftime("%a, %d %b %Y %H:%M:%S GMT")
        etag = check_etag(environ, timestamp)

        nav = Navigation(r.hits, q)
        search_term = q.getSearchTerm(cast=False)
        tvars=dict(hits=r.hits,
                   query=q,
                   count = q.getCount(),
                   updated = updated,
                   search_term = search_term,
                   start_index = nav.start_index,
                   end_index = nav.end_index,
                   next_links = nav.getNextLinks(),
                   prev_links = nav.getPrevLinks(),
                   last_link = nav.getLastLink(),
                   first_link = nav.getFirstLink(),
                   current_page = nav.current_page,
                   page_count = nav.page_count,
                   results=list(r))

        title = 'Results'

        area_name = q.getArea()
        if area_name:
            title += ' in %s' % area_name

        if r.hits:
            title += ' (page %d of %d)' % (nav.current_page, nav.page_count)

        if search_term:
            title += ' for: %s' % search_term

        # modify the headers. We need a local copy of the base headers
        # so we don't alter the instance
        headers = copy(self.headers)

        # propagate the result update time to the HTTP layer
        headers.append(('Etag', etag))

        return TemplateContext(title, tvars=tvars, headers=headers)

class HTMLResults(Results):
    def __init__(self):
        from medin.dws import RESULT_BRIEF
        
        headers = [('Content-type', 'text/html')]
        super(HTMLResults, self).__init__(['%s', 'catalogue.html'], headers, RESULT_BRIEF)

    def setup(self, environ):
        from copy import deepcopy

        # create the data structure for the template sort logic
        ctxt = super(HTMLResults, self).setup(environ)
        query = deepcopy(ctxt.tvars['query'])
        ctxt.tvars['criteria'] = query.asDict(False)

        sorts = {}
        cur_sort, cur_asc = query.getSort(default=('updated', 0))
        for sort in query.fields:
            query.setSort((sort, 1))
            asc = (str(query), (sort == cur_sort and cur_asc == 1))
            query.setSort((sort, 0))
            desc = (str(query), (sort == cur_sort and cur_asc == 0))
            sorts[sort] = dict(asc=asc, desc=desc)
        ctxt.tvars['sort'] = sorts

        return ctxt

class RSSResults(Results):
    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        headers = [('Content-type', 'application/rss+xml')]
        super(RSSResults, self).__init__(['rss', 'catalogue', '%s.xml'], headers, RESULT_SUMMARY)

class AtomResults(Results):
    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        headers = [('Content-type', 'application/atom+xml')]
        super(AtomResults, self).__init__(['atom', 'catalogue', '%s.xml'], headers, RESULT_SUMMARY)

class AreaResults(object):

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # we need to seed the query object with an area by translating
        # the area name to an area id

        areas = {'ices-rectangles': 'ir',
                 'countries': 'co',
                 'charting-progress': 'cp',
                 'sea-areas': 'sa'}

        area = environ['selector.vars']['area']
        name = environ['selector.vars']['name']
        
        try:
            area_type = areas[area]
        except KeyError:
            raise HTTPError('404 Not Found', 'The area is not recognised: %s' % area)
        
        areas = get_areas(environ)
        aid = areas.getAreaId(name, area_type)
        if not aid:
            raise HTTPError('404 Not Found', 'The area name is not recognised: %s' % name)
    
        q = get_query(environ)
        q.setArea(aid)
        set_query(q, environ)

        # delegate to the result app
        return self.app(environ, start_response)

class ResultSummary(object):

    def __init__(self):
        from medin.dws import SearchRequest
        
        self.request = SearchRequest()

    def __call__(self, environ, start_response):
        from medin.dws import RESULT_SIMPLE
        from json import dumps as tojson

        q = get_query(environ)
        q.setCount(0)                   # we don't need any results
        
        r = self.request(q, RESULT_SIMPLE, environ['logging.logger'])

        json = tojson({'status': bool(r),
                       'hits': r.hits,
                       'time': environ['portal.timer'].runtime()})
        
        headers = [('Content-type', 'application/json')]

        start_response('200 OK', headers)
        return [json]
    
class ResultFormat(object):

    def __init__(self, default, formats):
        self.default = default
        self.formats = formats

    def __call__(self, environ, start_response):
        try:
            fmt = environ['selector.vars']['format']
        except KeyError:
            app = self.default
        else:
            if fmt is not None:
                try:
                    app = self.formats[fmt]
                except KeyError:
                    raise HTTPError('404 Not Found', 'The format is not supported: %s' % fmt)
            else:
                app = self.default

        return app(environ, start_response)

class Metadata(MakoApp):

    def __init__(self, path):
        from medin.dws import MetadataRequest

        self.request = MetadataRequest()
        super(Metadata, self).__init__(path, check_etag=False)

    def setup(self, environ):

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        parser = self.request(gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        headers = []
        if parser:
            etag = check_etag(environ, parser.date())
            headers.append(('Etag', etag))

        return parser, headers

class MetadataHTML(Metadata):
    def __init__(self):
        from medin.dws import SearchRequest
        self.search_request = SearchRequest()
        super(MetadataHTML, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        from medin.dws import RESULT_SIMPLE
        
        parser, headers = super(MetadataHTML, self).setup(environ)

        q = get_query(environ)
        criteria = q.asDict(False)
        r = self.search_request(q, RESULT_SIMPLE, environ['logging.logger'])

        metadata = parser.parse()
        title = 'Metadata: %s' % metadata.title
        tvars = dict(metadata=metadata,
                     criteria=criteria,
                     hits=r.hits)

        headers.append(('Content-type', 'text/html'))

        return TemplateContext(title, tvars=tvars, headers=headers)

class MetadataKML(Metadata):
    def __init__(self):
        super(MetadataKML, self).__init__(['kml', 'catalogue', 'metadata-%s.kml'])

    def setup(self, environ):
        parser, headers = super(MetadataKML, self).setup(environ)

        if parser:
            title = parser.title()
            tvars = dict(gid=parser.uid,
                         bbox=parser.bbox(),
                         author=parser.author(),
                         abstract=parser.abstract())
        else:
            title = ''
            tvars = {}

        filename = parser.uniqueID()
        if not filename: filename = 'metadata.kml'
        else: filename += '.kml'
        
        headers.extend((('Content-type', 'application/vnd.google-earth.kml+xml'),
                        ('Content-disposition', 'attachment; filename="%s"' % filename)))

        return TemplateContext(title, tvars=tvars, headers=headers)

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

def background_raster(template_lookup, environ):
    """Return the background raster filepath

    The filepath is to a temporary file, which is created the first
    time this function is called."""

    global _bg_raster
    try:
        return _bg_raster
    except NameError:
        pass

    import os.path
    from mako.runtime import Context

    raster = 'background-wms.xml'
    templatepath = os.path.join('config', raster)
    template = template_lookup.get_template(templatepath)
    rasterpath = os.path.join(environ.root, 'tmp', raster)

    # render the template to the file
    fh = open(rasterpath, 'w')
    ctx = Context(fh, resource_root=environ.script_uri())
    template.render_context(ctx)
    fh.close()

    _bg_raster = rasterpath
    return rasterpath

class MetadataImage(object):
    """
    WSGI app for outputting a metadata image
    """

    def __init__(self):
        from medin.dws import MetadataRequest
        self.request = MetadataRequest()

    def __call__(self, environ, start_response):
        import os.path
        import medin.spatial

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        parser = self.request(gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        etag = check_etag(environ, parser.date())

        bbox = parser.bbox()
        if not bbox:
            raise HTTPError('404 Not Found', 'The metadata record does not have a geographic bounding box')

        # ensure the background raster datasource has been created
        template_lookup = TemplateLookup(environ)
        lookup = template_lookup.lookup()
        rasterpath = background_raster(lookup, environ)

        # create the mapfile from its template
        mappath = os.path.join('config', 'metadata-extent.xml')
        template = lookup.get_template(mappath)
        mapfile = template.render(root_dir=environ.root)

        # create the image
        image = medin.spatial.metadata_image(bbox, mapfile)

        # serialise the image
        bytes = image.tostring('png')

        headers = [('Content-Type', 'image/png'),
                   ('Etag', etag)]

        start_response('200 OK', headers)
        return [bytes]

class MetadataXML(object):
    """
    WSGI app for downloading metadata in XML format
    """

    def __init__(self):
        from medin.dws import MetadataRequest
        self.request = MetadataRequest()

    def __call__(self, environ, start_response):
        from os.path import splitext

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        fmt = environ['selector.vars']['format'] # the requested format

        if fmt not in self.request.getMetadataFormats():
            raise HTTPError('404 Not Found', 'The metadata format is not supported: %s' % fmt)

        areas = get_areas(environ)
        parser = self.request(gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        etag = check_etag(environ, parser.date())

        filename = parser.uniqueID()
        if not splitext(filename)[1]:
            filename += '.xml'

        document = str(parser.document)

        headers = [('Content-disposition', 'attachment; filename="%s"' % filename),
                   ('Content-Type', 'application/xml'),
                   ('Etag', etag)]

        start_response('200 OK', headers)
        return [document]

class MetadataCSV(object):
    """
    WSGI app for downloading metadata in CSV format
    """

    def __init__(self):
        from medin.dws import MetadataRequest
        self.request = MetadataRequest()

    def __call__(self, environ, start_response):
        import csv, itertools
        from cStringIO import StringIO
        from itertools import repeat

        def iter_element_values(element_no, element_title, values):
            """Returns an iterator suitable for passing to the CSV writerows method"""

            if isinstance(values, Exception):
                values = [['ERROR', values.message, values.detail]]
            elif not values:
                values = ['']
            
            for title, value in itertools.izip(itertools.chain([[element_no, element_title]], itertools.repeat(['', ''], len(values)-1)), values):
                try:
                    # it's a row
                    yield title + value
                except TypeError:
                    # it's a scalar value
                    yield title + [value]

        def iter_contacts(contacts, depth=0):
            if isinstance(contacts, Exception):
                yield ['ERROR', contacts.message, contacts.detail]
                raise StopIteration('End of error')
            
            for contact in contacts:
                for attr in ('organisation', 'address', 'tel', 'fax', 'email', 'name', 'position'):
                    val = getattr(contact, attr)
                    if not val:
                        continue

                    row = list(repeat(None, depth))
                    row.extend((attr.capitalize(), val))
                    yield row

                for role in contact.roles:
                    row = list(repeat(None, depth))
                    row.extend(('Role', role))
                    yield row

                for row in iter_contacts(contact.contacts, depth+1):
                    yield row

        def write_element(writer, number, name, element):
            if isinstance(element, Exception):
                row = [number, name, 'ERROR', element.message, element.detail]
            else:
                row = [number, name, element]

            writer.writerow(row)
        
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)
        parser = self.request(gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        etag = check_etag(environ, parser.date())

        metadata = parser.parse()

        buf = StringIO()
        writer = csv.writer(buf)

        writer.writerow(['Element number', 'Element title', 'Element Values']) # header row

        write_element(writer, 1, 'Title', metadata.title)
        writer.writerows(iter_element_values(2, 'Alternative resource title', metadata.alt_titles))
        write_element(writer, 3, 'Abstract', metadata.abstract)
        write_element(writer, 4, 'Resource type', metadata.resource_type)

        row = metadata.online_resource
        if row and not isinstance(row, Exception):
            row = [[i['link'], i['name'], i['description']] for i in row]
        writer.writerows(iter_element_values(5, 'Resource locator', row))

        write_element(writer, 6, 'Unique resource identifier', metadata.unique_id)
        writer.writerow([7, 'Coupled resource', 'NOT IMPLEMENTED IN THE PORTAL YET'])
        write_element(writer, 8, 'Resource language', metadata.resource_language)

        row = metadata.topic_category
        if row and not isinstance(row, Exception):
            tmp = []
            for keyword, defn in row.items():
                entry = []
                if defn:
                    if 'error' in defn:
                        entry.append(defn['error'])
                    elif defn['long'] != defn['short']:
                        entry.extend((defn['short'], defn['long']))
                    else:
                        entry.append(defn['short'])
                else:
                    entry.append(keyword)

                tmp.append(entry)
            row = tmp
        writer.writerows(iter_element_values(9, 'Topic category', row))

        writer.writerows(iter_element_values(10, 'Spatial data service type', metadata.service_type))

        row = metadata.keywords
        if row and not isinstance(row, Exception):
            tmp = []
            for title, defns in row.items():
                for keyword, defn in defns.items():
                    entry = [title]
                    if defn:
                        if 'error' in defn:
                            entry.append(defn['error'])
                        elif defn['long'] != defn['short']:
                            entry.extend((defn['short'], defn['long']))
                        else:
                            entry.append(defn['short'])
                    else:
                        entry.append(keyword)

                    tmp.append(entry)
            row = tmp
        writer.writerows(iter_element_values(11, 'Keywords', row))

        row = metadata.bbox
        if row and not isinstance(row, Exception):
            row = [['West', metadata.bbox[0]],
                    ['South', metadata.bbox[1]],
                    ['East', metadata.bbox[2]],
                    ['North', metadata.bbox[3]]]
        writer.writerows(iter_element_values(12, 'Geographic extent', row))

        row = metadata.extents
        if row and not isinstance(row, Exception):
            row = [[i['title'], i['name']] for i in row]
        writer.writerows(iter_element_values(13, 'Extent', row))

        writer.writerows(iter_element_values(14, 'Vertical extent information', metadata.vertical_extent))

        row = metadata.reference_system
        if row and not isinstance(row, Exception):
            tmp = []
            for key in ('identifier', 'source', 'url', 'name', 'scope'):
                if not row[key]:
                    continue
                tmp.append((key.capitalize(), row[key]))
            row = tmp
        writer.writerows(iter_element_values(15, 'Spatial reference system', row))

        row = metadata.temporal_reference
        if row and not isinstance(row, Exception):
            tmp = []
            if 'range' in row:
                tmp.append(['Data start', str(row['range'][0])])
                tmp.append(['Data end', str(row['range'][1])])

            row = tmp + [[code, str(date)] for code, date in row['single']]
        writer.writerows(iter_element_values(16, 'Temporal reference', row))

        write_element(writer, 17, 'Lineage', metadata.lineage)

        row = metadata.spatial_resolution
        if row and not isinstance(row, Exception):
            tmp = []
            for entry in row:
                if 'distance' in entry:
                    tmp.append(['Distance (m)', entry['distance']])
                if 'scale' in entry:
                    tmp.append(['Scale 1:', entry['scale']])
            row = tmp
        writer.writerows(iter_element_values(18, 'Spatial resolution', row))
        
        write_element(writer, 19, 'Additional information', metadata.additional_info)
        writer.writerows(iter_element_values(20, 'Limitations on public access', metadata.access_limits))
        writer.writerows(iter_element_values(21, 'Conditions for access and use constraints', metadata.access_conditions))
        writer.writerows(iter_element_values(22, 'Responsible party', list(iter_contacts(metadata.responsible_party))))
        writer.writerows(iter_element_values(23, 'Data format', metadata.data_format))
        write_element(writer, 24, 'Frequency of update', metadata.update_frequency)
        write_element(writer, 25, 'INSPIRE conformity', 'NOT IMPLEMENTED IN THE PORTAL YET')

        date = metadata.date
        if date and not isinstance(date, Exception): date = str(date)
        write_element(writer, 26, 'Date of update of metadata', date)

        write_element(writer, 27, 'Metadata standard name', metadata.name)  
        write_element(writer, 28, 'Metadata standard version', metadata.version)
        write_element(writer, 29, 'Metadata language', metadata.language)

        buf.seek(0)                     # point to the start of the buffer

        if metadata.unique_id:
            filename = metadata.unique_id + '.csv'
        else:
            filename = gid + '.csv'

        headers = [('Content-disposition', 'attachment; filename="%s"' % filename),
                   ('Content-Type', 'application/vnd.ms-excel'),
                   ('Etag', etag)]

        start_response('200 OK', headers)
        return buf

class TemplateChoice(MakoApp):
    def __init__(self):
        super(TemplateChoice, self).__init__(['light', 'templates.html'], False)

    def setup(self, environ):
        return TemplateContext('Choose Your Search Format')

def query_criteria(environ, start_response):
    from json import dumps as tojson
    
    q = get_query(environ)
    
    # Check if the client needs a new version
    etag = check_etag(environ, str(q))

    json = tojson(q.asDict())
    
    headers = [('Content-Type', 'application/json'),
               ('Etag', etag)]
    
    start_response('200 OK', headers)
    return [json]

def get_bbox(environ, start_response):
    from json import dumps as tojson
    from medin.spatial import Areas

    aid = environ['selector.vars']['id'] # the area ID
    
    # Check if the client needs a new version
    etag = check_etag(environ, aid)

    bbox = Areas(get_db(environ)).getBBOX(aid)
    if not bbox:
        raise HTTPError('404 Not Found', 'The area id does not exist: %s' % aid)

    json = tojson(bbox)
    
    headers = [('Content-Type', 'application/json'),
               ('Etag', etag)]
    
    start_response('200 OK', headers)
    return [json]

def proxy(environ, start_response):
    from medin.query import GETParams

    params = GETParams(environ.get('QUERY_STRING', ''))
    try:
        url = params['url'][0]
    except KeyError:
        url = ''

    valid_proxies = ('http://www.dassh.ac.uk:8081/geoserver/wfs',)
    if not url.startswith(valid_proxies):
        raise HTTPError('403 Forbidden', 'The url cannot be proxied: %s' % url)

    import urllib2
    response = urllib2.urlopen(url)
    try:
        response = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        raise HTTPError('%d Error' % e.getcode(), str(e))
    except urllib2.URLError, e:
        try:
            status, msg = e.reason
        except ValueError:
            msg = str(e.reason)
            status = 500
    
        raise HTTPError('%d Error' % status, msg)

    # remove hop-by-hop headers (as defined at http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)
    for header in ('Keep-Alive', 'Proxy-Authenticate', 'Proxy-Authorization', 'TE', 'Trailers', 'Transfer-Encoding', 'Upgrade', 'Connection', 'Server'):
        del response.headers[header]
        
    headers = response.headers.items()
    start_response('%s OK' % response.getcode(), headers)
    return response

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

class Selector(selector.Selector):
    status404 = medin.error.HTTPErrorRenderer('404 Not Found', 'The resource you specified could not be found')

def wsgi_app():
    """
    Return an instance of the Portal's root WSGI application
    """
    
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
    application.add('/spatial/areas/{id:word}/extent.json', GET=get_bbox)

    # provide a choice of templates
    application.add('[/]', GET=TemplateChoice())

    # the OpenSearch Description document
    application.add('/opensearch/catalogue/{template}.xml', GET=OpenSearch())

    # the default entry point for the search
    app = Search()
    application.add('/{template}[/]',
                    GET=app,
                    POST=config(Comment(app)))

    # the API for analysing search criteria passed in via GET parameters
    application.add('/{template}/query.json', GET=query_criteria)

    # retrieve the result summary for a query
    application.add('/{template}.json', GET=ResultSummary())

    # create the app to return the required formats
    app = HTMLResults()
    result_formats = medin.ResultFormat(app, {'rss': RSSResults(),
                                              'atom': AtomResults()})

    # search by country
    application.add('/{template}/areas/{area:segment}/{name:segment}',
                    GET=AreaResults(result_formats),
                    POST=config(Comment(AreaResults(app))))

    # display and navigate through the result set
    application.add('/{template}/catalogue[.{format:word}]',
                    GET=result_formats,
                    POST=config(Comment(app)))

    # display the metadata
    app = MetadataHTML()
    application.add('/{template}/catalogue/{gid:segment}',
                    GET=app,
                    POST=config(Comment(app)))

    # get the metadata as in KML format
    application.add('/{template}/catalogue/{gid:segment}/kml', GET=MetadataKML())

    # get an image representing the metadata bounds.
    application.add('/{template}/catalogue/{gid:segment}/extent.png', GET=MetadataImage())

    # download the metadata as CSV
    application.add('/{template}/catalogue/{gid:segment}/csv', GET=MetadataCSV())

    # download the metadata as XML
    application.add('/{template}/catalogue/{gid:segment}/{format:segment}', GET=MetadataXML())

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
