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
Portal views

The views are WSGI applications and are responsible for creating HTTP
resources. They create the content that the HTTP client receives when
visiting a particular URI.
"""

from errata import HTTPError

# Custom modules
from medin.templates import TemplateLookup, MakoApp, TemplateContext
from medin.log import msg_info, msg_warn, msg_error
from medin.metadata import MetadataError

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
    from medin import __version__

    # format the etag to include the application version
    server_etag = '"%s (v%s)"' % (etag.encode('ascii', 'ignore'), str(__version__))

    try:
        client_etag = environ['HTTP_IF_NONE_MATCH']
    except KeyError:
        pass
    else:
        if server_etag == client_etag:
            raise HTTPNotModified

    return server_etag

def get_metadata_date(environ, parser):
    """
    Return the metadata date as a string

    If the date cannot be retrieved the error is logged.
    """
    try:
        return str(parser.date())
    except MetadataError, e:
        environ['logging.logger'].exception('The metadata date cannot be retrieved')

    return None

def set_query(query, environ):
    environ['QUERY_STRING'] = str(query)

def get_query(environ, from_referrer=False):
    """Returns an object encapsulating the OpenSearch query parameters

    The query is obtained from the environ QUERY_STRING variable by
    default or the HTTP_REFERER query string if the from_referrer
    parameter is True.
    """
    from medin.query import Query

    if not from_referrer:
        try:
            qsl = environ['QUERY_STRING']
        except KeyError:
            qsl = ''
    else:
        try:
            referrer = environ['HTTP_REFERER']
        except KeyError:
            qsl = ''
        else:
            # check whether the referral is from the portal
            if referrer.startswith(environ.script_uri()):
                from urlparse import urlparse
        
                url = urlparse(referrer)
                qsl = url.query
            else:
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

# The WSGI Applications

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
                server = 'localhost'
            try:
                port = config.get('SMTP', 'port')
            except NoOptionError:
                port = 25

            if not email: from_addr = '"MEDIN Portal Comment" <%s>' % to_addr
            else: from_addr = email

            # email the comment
            self.sendComment(from_addr, to_addr, subject, msg, server, port)
            msg_info(environ, 'Thank you for your comment')
        
        # delegate to the wrapped app
        return self.app(environ, start_response)

class OpenSearch(MakoApp):
    def __init__(self):
        super(OpenSearch, self).__init__(['opensearch', 'catalogue', '%s.xml'],
                                         content_type='application/opensearchdescription+xml')

    def setup(self, environ):
        title = 'MEDIN Catalogue'
        headers = [('Cache-Control', 'max-age=3600, must-revalidate')]
        return TemplateContext(title, headers=headers)

class Search(MakoApp):
    def __init__(self):
        from medin.dws import SearchRequest
        from medin.terms import MEDINVocabulary

        self.request = SearchRequest()
        self.vocab = MEDINVocabulary()
        super(Search, self).__init__(['%s', 'search.html'], check_etag=False)

    def setup(self, environ):
        from medin.dws import RESULT_SIMPLE
        from medin.terms import VocabError
        
        areas = get_areas(environ)
        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        # We need to get the number of hits for the query.
        # firstly save the current count setting:
        count = q.getCount(default=None)
        q.setCount(0)                   # we only need one result

        # secondly get the results in descending order so the result
        # can be used in an etag (as it is the latest).
        sort = q.getSort(cast=False)
        q.setSort('updated,0')

        # run the query
        r = self.request(q, RESULT_SIMPLE, environ['logging.logger'])

        # check the etag
        try:
            docid = list(r)[0]
        except IndexError:
            docid = 'none'
        etag = check_etag(environ, docid)

        # revert the query to its previous state
        if count is not None:
            q.setCount(count) # reset the count to it's previous value
        else:
            q.delCount() # delete the count as it wasn't there originally
        if sort is not None:
            q.setSort(sort)
        else:
            q.delSort()
        
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

        # get the vocabulary lists
        try:
            params = self.vocab.getList('P021')
        except VocabError, e:
            msg = 'The parameter list could not be retrieved'
            msg_error(environ, msg)
            environ['logging.logger'].exception(msg)
            params = None
        try:
            topics = self.vocab.getList('P051')
        except VocabError, e:
            msg = 'The topic category list could not be retrieved'
            msg_error(environ, msg)
            environ['logging.logger'].exception(msg)
            topics = None
        try:
            formats = self.vocab.getList('M010')
        except VocabError, e:
            msg = 'The data format list could not be retrieved'
            msg_error(environ, msg)
            environ['logging.logger'].exception(msg)
            formats = None
        resources = self.vocab.getList('resource-types')
        access = self.vocab.getList('access-types')

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
                   parameters=params,
                   topic_categories=topics,
                   data_formats=formats,
                   resource_types=resources,
                   access_types=access,
                   bbox=bbox)

        headers = [('Etag', etag), # propagate the result update time to the HTTP layer
                   ('Cache-Control', 'no-cache, must-revalidate')]

        return TemplateContext('Search the MEDIN Data Archive Centres', tvars=tvars, headers=headers)

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

    def __init__(self, path, result_type, **kwargs):
        from medin.dws import SearchRequest
        
        self.result_type = result_type
        self.request = SearchRequest()
        super(Results, self).__init__(path, check_etag=False, **kwargs)

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

        headers = [('Etag', etag), # propagate the result update time to the HTTP layer
                   ('Cache-Control', 'no-cache, must-revalidate')] # add the cache controls

        return TemplateContext(title, tvars=tvars, headers=headers)

class HTMLResults(Results):
    def __init__(self):
        from medin.dws import RESULT_BRIEF
        
        super(HTMLResults, self).__init__(['%s', 'catalogue.html'], RESULT_BRIEF)
        
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

        super(RSSResults, self).__init__(['rss', 'catalogue', '%s.xml'], RESULT_SUMMARY,
                                         content_type='application/rss+xml')

class AtomResults(Results):
    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        super(AtomResults, self).__init__(['atom', 'catalogue', '%s.xml'], RESULT_SUMMARY,
                                          content_type='application/atom+xml')

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
        
        headers = [('Content-Type', 'application/json')]

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

    def __init__(self, path, **kwargs):
        from medin.dws import MetadataRequest

        self.request = MetadataRequest()
        super(Metadata, self).__init__(path, check_etag=False, **kwargs)

    def setup(self, environ, etag_data=''):

        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        parser = self.request(environ['logging.logger'], gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        headers = []
        if parser:
            # check the etag, adding any extra data to the etag
            date = get_metadata_date(environ, parser)
            if date:
                etag = check_etag(environ, date+etag_data)
                headers.extend([('Etag', etag),
                                ('Cache-Control', 'no-cache, must-revalidate')])

        return parser, headers

class MetadataHTML(Metadata):
    def __init__(self):
        from medin.dws import SearchRequest
        self.search_request = SearchRequest()

        super(MetadataHTML, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        from medin.dws import RESULT_SIMPLE
        
        q = get_query(environ, True)    # get the query from the HTTP referrer
        referrer_query_string = str(q)

        # call the base setup, using the referrer query string as etag data
        parser, headers = super(MetadataHTML, self).setup(environ, referrer_query_string)

        criteria = q.asDict(False)
        r = self.search_request(q, RESULT_SIMPLE, environ['logging.logger'])

        if referrer_query_string: referrer_query_string = '?'+referrer_query_string
        metadata = parser.parse()
        title = 'Metadata: %s' % metadata.title
        tvars = dict(metadata=metadata,
                     criteria=criteria,
                     referrer_query_string=referrer_query_string,
                     hits=r.hits)

        return TemplateContext(title, tvars=tvars, headers=headers)

class MetadataKML(Metadata):
    def __init__(self):
        super(MetadataKML, self).__init__(['kml', 'catalogue', 'metadata-%s.kml'],
                                          content_type='application/vnd.google-earth.kml+xml')

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
        
        headers.append(('Content-disposition', 'attachment; filename="%s"' % filename))

        return TemplateContext(title, tvars=tvars, headers=headers)

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

        parser = self.request(environ['logging.logger'], gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        headers = []
        date = get_metadata_date(environ, parser)
        if date:            
            etag = check_etag(environ, date)
            headers.extend([('Etag', etag),
                            ('Cache-Control', 'no-cache, must-revalidate')])

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

        headers.append(('Content-Type', 'image/png'))

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

        if fmt not in self.request.getMetadataFormats(environ['logging.logger']):
            raise HTTPError('404 Not Found', 'The metadata format is not supported: %s' % fmt)

        areas = get_areas(environ)
        parser = self.request(environ['logging.logger'], gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        headers = []
        date = get_metadata_date(environ, parser)
        if date:            
            etag = check_etag(environ, date)
            headers.extend([('Etag', etag),
                            ('Cache-Control', 'no-cache, must-revalidate')])

        filename = parser.uniqueID()
        if not splitext(filename)[1]:
            filename += '.xml'

        document = str(parser.document)

        headers.extend([('Content-disposition', 'attachment; filename="%s"' % filename),
                        ('Content-Type', 'application/xml')])

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
        parser = self.request(environ['logging.logger'], gid, areas)
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        headers = []
        date = get_metadata_date(environ, parser)
        if date:            
            etag = check_etag(environ, date)
            headers.extend([('Etag', etag),
                            ('Cache-Control', 'no-cache, must-revalidate')])

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

        headers.extend([('Content-disposition', 'attachment; filename="%s"' % filename),
                        ('Content-Type', 'application/vnd.ms-excel')])

        start_response('200 OK', headers)
        return buf

class TemplateChoice(MakoApp):
    def __init__(self):
        super(TemplateChoice, self).__init__(['light', 'templates.html'], False)

    def setup(self, environ):
        headers = [('Cache-Control', 'max-age=3600, must-revalidate')]
        return TemplateContext('Choose Your Search Format', headers=headers)

def query_criteria(environ, start_response):
    from json import dumps as tojson
    
    q = get_query(environ)
    
    # Check if the client needs a new version
    etag = check_etag(environ, str(q))

    json = tojson(q.asDict())
    
    headers = [('Content-Type', 'application/json'),
               ('Etag', etag),
               ('Cache-Control', 'max-age=3600, must-revalidate')]
    
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
               ('Etag', etag),
               ('Cache-Control', 'max-age=3600, must-revalidate')]
    
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
    response = urllib2.urlopen(url, timeout=5)
    try:
        response = urllib2.urlopen(url, timeout=5)
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

class ErrorRenderer(MakoApp):
    """
    A view to render an exception to the user interface.
    """
    def __init__(self, exception):
        super(ErrorRenderer, self).__init__(['%s', 'error.html'], check_etag=False)
        self.exception = exception

    def setup(self, environ):
        title = 'Error - %s' % self.exception.args[0]
        status = self.exception.args[0]
        tvars = dict(message=self.exception.args[1])
        return TemplateContext(title, status=status, tvars=tvars)
