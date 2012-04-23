# -*- coding: utf-8 -*-
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

# Output filters that can be added to `templates.MakoApp.filters`
import re
class ObfuscateEmails(object):
    """
    Obfuscate email addresses by encoding them as XML entities
    """

    # A regular expression to match email addresses (adapted from http://www.noah.org/wiki/RegEx_Python#email_regex_pattern)
    _email_pattern = re.compile(r"""((mailto:)?[a-zA-Z0-9+_\-\.]+@[0-9a-zA-Z][.-0-9a-zA-Z]*\.[a-zA-Z]+)""")

    def __call__(self, text):
        return self._email_pattern.sub(lambda x: ''.join(['&#' + hex(ord(i))[1:] + ';' for i in x.group()]), text);

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
        comment = form.getfirst('comment').strip()
        check = form.getfirst('comment-check')
        question = form.getfirst('comment-question').strip()
        request_uri = environ.request_uri()
        submit = True

        if check:
            # try and catch any spam bots as they usually fill in hidden fields
            msg_warn(environ, 'The comment failed the spam filter and was not submitted')
            submit = False
        if question.lower() != 'environmental':
            msg_warn(environ, 'Please answer the question correctly in order to submit your comment')
            submit = False
        if environ.get('HTTP_REFERER') != request_uri:
            msg_error(environ, 'The comment must be submitted from the appropriate page')
            submit = False
        if not comment:
            msg_warn(environ, 'You did not fill in the comment field')
            submit = False

        if submit:
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

        self.filters.append(ObfuscateEmails()) # ensure emails are obfuscated when rendered

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

        self.filters.append(ObfuscateEmails()) # ensure emails are obfuscated when rendered

    def prepareSOAP(self, environ):
        """
        The interface for generating a SOAPCaller
        """
        from medin.dws import RESULT_SIMPLE

        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        q.setCount(0)                   # we only need one result

        # Get the results in descending order so the result can be
        # used in an etag (as it is the latest).
        sort = q.getSort(cast=False)
        q.setSort('updated,0')

        # generate the soap caller
        return self.request.prepareCaller(q, RESULT_SIMPLE, environ['logging.logger'])

    def setup(self, environ):
        from medin.terms import VocabError

        # run the query
        self.prepareSOAP(environ)
        r = self.request()

        # check the etag
        try:
            docid = list(r)[0]
        except IndexError:
            docid = 'none'
        etag = check_etag(environ, docid)

        areas = get_areas(environ)
        q = get_query(environ)

        count = q.getCount(default=None) # We need to get the number of hits for the query.
        search_term = q.getSearchTerm(cast=False)
        sort = q.getSort(cast=False)
        bboxes = q.getBoxes()
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
                   bboxes=bboxes)

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

class ResultsRequest(object):
    """
    Perform a request to obtain results from the DWS for a search

    This class is needed as it encapsulates the request. The result of
    the request can then be formatted as required, e.g. either by
    MakoAppResults or CSVResults.
    """

    def __init__(self, result_type):
        from medin.dws import SearchRequest

        self.result_type = result_type
        self.request = SearchRequest()

    def prepareSOAP(self, environ):
        """
        The interface for generating a SOAPCaller
        """
        q = get_query(environ)
        errors = q.verify()
        if errors:
            for error in errors:
                msg_error(environ, error)

        return self.request.prepareCaller(q, self.result_type, environ['logging.logger'])

    def __call__(self, environ):
        self.prepareSOAP(environ)
        r = self.request()

        updated = r.lastModified()
        timestamp = updated.strftime("%a, %d %b %Y %H:%M:%S GMT")
        etag = check_etag(environ, timestamp)

        return r, etag

class Results(MakoApp):

    def __init__(self, path, result_type, **kwargs):
        from medin.dws import SearchRequest

        self.request = ResultsRequest(result_type)
        super(Results, self).__init__(path, check_etag=False, **kwargs)

        self.filters.append(ObfuscateEmails()) # ensure emails are obfuscated when rendered

    def prepareSOAP(self, environ):
        return self.request.prepareSOAP(environ)

    def setup(self, environ):
        r, etag = self.request(environ);

        q = get_query(environ)
        nav = Navigation(r.hits, q)
        search_term = q.getSearchTerm(cast=False)
        tvars=dict(hits=r.hits,
                   query=q,
                   count = q.getCount(),
                   updated = r.lastModified(),
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
        from medin.terms import Vocabulary

        super(HTMLResults, self).__init__(['%s', 'catalogue.html'], RESULT_BRIEF)
        self.vocab = Vocabulary()

    def setup(self, environ):
        from copy import deepcopy

        # create the data structure for the template sort logic
        ctxt = super(HTMLResults, self).setup(environ)
        query = deepcopy(ctxt.tvars['query'])

        # set up the related terms mapping
        mapping = {}
        for op_or, op_not, target, word in query.getSearchTerm(skip_errors=True):
            related = self.vocab.getRelated('P211', word.strip('"'))
            if not related:
                continue
            mapping[word] = related
        ctxt.tvars['mapping'] = mapping

        # set up the sort criteria
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

class KMLResults(Results):
    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        super(KMLResults, self).__init__(['kml', 'catalogue', '%s.xml'], RESULT_SUMMARY,
                                         content_type='application/vnd.google-earth.kml+xml')

class CSVResults(Results):
    """
    Display the results in CSV format

    This is not an XML based format like the other result formats, so
    must be implemented differently.
    """

    def __init__(self):
        from medin.dws import RESULT_SUMMARY

        self.request = ResultsRequest(RESULT_SUMMARY)

    def prepareSOAP(self, environ):
        return self.request.prepareSOAP(environ)

    def __call__(self, environ, start_response):
        from cStringIO import StringIO
        import csv

        results, etag = self.request(environ)

        buf = StringIO()
        writer = csv.writer(buf)

        writer.writerow([
                'ID',
                'Title',
                'Updated',
                'Authors',
                'URL',
                'Abstract',
                'Originator',
                'Resource type',
                'Topic category',
                'Lineage',
                'Public access',
                'Format',
                'Parameters',
                'West',
                'East',
                'South',
                'North'])
        for result in results:
            url = "%s/full/catalogue/%s" % (environ.script_uri(), result['id'])
            row = [
                result['id'],
                result['title'],
                result['updated'],
                '; '.join(result['authors']),
                url,
                result['abstract'],
                result['originator'],
                result['resource-type'],
                result['topic-category'],
                result['lineage'],
                result['public-access'],
                result['format'],
                '; '.join(result['parameters'])
                ]

            if result['bbox']:
                # get the total extent of multiple bounding boxes
                bbox = [
                    min((box[0] for box in result['bbox'])),
                    min((box[1] for box in result['bbox'])),
                    max((box[2] for box in result['bbox'])),
                    max((box[3] for box in result['bbox']))]

                row.extend([
                        bbox[0],
                        bbox[2],
                        bbox[1],
                        bbox[3]])
            else:
                row.extend(['', '', '', ''])

            writer.writerow(row)
        buf.seek(0)

        headers = [('Etag', etag), # propagate the result update time to the HTTP layer
                   ('Cache-Control', 'no-cache, must-revalidate'), # add the cache controls
                   ('Content-Type', 'application/vnd.ms-excel'),
                   ('Content-disposition', 'attachment; filename="results.csv"')]

        start_response('200 OK', headers)
        return buf

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

    def prepareSOAP(self, environ):
        """
        The interface for generating a SOAPCaller
        """
        from medin.dws import RESULT_SIMPLE

        q = get_query(environ)
        q.setCount(0)                   # we don't need any results

        return self.request.prepareCaller(q, RESULT_SIMPLE, environ['logging.logger'])

    def __call__(self, environ, start_response):
        from json import dumps as tojson

        self.prepareSOAP(environ)
        r = self.request()

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
        from medin.dws import MedinMetadataRequest

        self.request = MedinMetadataRequest()
        super(Metadata, self).__init__(path, check_etag=False, **kwargs)

    def prepareSOAP(self, environ):
        """
        The interface for generating a SOAPCaller
        """
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        return self.request.prepareCaller(environ['logging.logger'], gid, areas)

    def setup(self, environ, etag_data=''):

        self.prepareSOAP(environ)
        parser = self.request()
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % environ['selector.vars']['gid'])

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
        import re
        from medin.dws import SearchRequest
        self.search_request = SearchRequest()

        super(MetadataHTML, self).__init__(['%s', 'metadata.html'])

        # see http://daringfireball.net/2010/07/improved_regex_for_matching_urls
        self.url_pattern = re.compile(r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""")

        self.filters.append(ObfuscateEmails()) # ensure emails are obfuscated when rendered

    def setup(self, environ):
        from medin.dws import RESULT_SIMPLE

        q = get_query(environ, True)    # get the query from the HTTP referrer
        referrer_query_string = str(q)

        # call the base setup, using the referrer query string as etag data
        parser, headers = super(MetadataHTML, self).setup(environ, referrer_query_string)

        criteria = q.asDict(False)
        self.search_request.prepareCaller(q, RESULT_SIMPLE, environ['logging.logger'])
        r = self.search_request()

        if referrer_query_string: referrer_query_string = '?'+referrer_query_string
        metadata = parser.parse()
        title = 'Metadata: %s' % metadata.title

        # urlify strings
        if metadata.additional_info:
            metadata.additional_info = self.urlify(metadata.additional_info)

        custodians = [contact.organisation for contact in metadata.responsible_party.getContactsForRole('custodian')]

        tvars = dict(metadata=metadata,
                     criteria=criteria,
                     referrer_query_string=referrer_query_string,
                     custodians=custodians,
                     hits=r.hits)

        return TemplateContext(title, tvars=tvars, headers=headers)

    def urlify(self, text):
        """
        Create active HTML links out of plain text URLs
        """

        # see http://stackoverflow.com/questions/520031/whats-the-cleanest-way-to-extract-urls-from-a-string-using-python
        return self.url_pattern.sub(lambda x: '<a href="%(url)s">%(url)s</a>' % dict(url=str(x.group())), text);

class MetadataKML(Metadata):
    def __init__(self):
        super(MetadataKML, self).__init__(['kml', 'catalogue', 'metadata-%s.kml'],
                                          content_type='application/vnd.google-earth.kml+xml')

    def setup(self, environ):
        parser, headers = super(MetadataKML, self).setup(environ)

        if parser:
            title = parser.title()
            tvars = dict(gid=parser.uid,
                         bboxes=parser.bboxes(),
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
        from medin.dws import MedinMetadataRequest
        self.request = MedinMetadataRequest()

    def prepareSOAP(self, environ):
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        return self.request.prepareCaller(environ['logging.logger'], gid, areas)

    def __call__(self, environ, start_response):
        import os.path
        import medin.spatial

        self.prepareSOAP(environ)
        parser = self.request()
        if not parser:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        # Check if the client needs a new version
        headers = []
        date = get_metadata_date(environ, parser)
        if date:
            etag = check_etag(environ, date)
            headers.extend([('Etag', etag),
                            ('Cache-Control', 'no-cache, must-revalidate')])

        bboxes = parser.bboxes()
        if not bboxes:
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
        image = medin.spatial.metadata_image(bboxes, mapfile)

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

        self.obfuscate_emails = ObfuscateEmails() # ensure emails are obfuscated when rendered

    def prepareSOAP(self, environ):
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        fmt = environ['selector.vars']['format'] # the requested format

        if fmt not in self.request.getMetadataFormats(environ['logging.logger']):
            raise HTTPError('404 Not Found', 'The metadata format is not supported: %s' % fmt)

        self.gid = gid
        self.fmt = fmt
        return self.request.prepareCaller(environ['logging.logger'], gid, fmt)

    def __call__(self, environ, start_response):
        from os.path import splitext

        self.prepareSOAP(environ)
        gid, fmt = self.gid, self.fmt
        response = self.request()
        if not response:
            raise HTTPError('404 Not Found', 'The metadata record does not exist: %s' % gid)

        document = self.obfuscate_emails(response.xml)
        if not document:
            raise HTTPError('404 Not Found', 'The metadata format does not contain any data: %s' % fmt)

        # Check if the client needs a new version
        headers = []
        date = response.date
        if date:
            etag = check_etag(environ, date)
            headers.extend([('Etag', etag),
                            ('Cache-Control', 'no-cache, must-revalidate')])

        filename = gid
        if splitext(filename)[1] != '.xml':
            filename += '.xml'

        headers.extend([('Content-disposition', 'attachment; filename="%s"' % filename),
                        ('Content-Type', 'application/xml')])

        start_response('200 OK', headers)
        return [document]

class MetadataCSV(object):
    """
    WSGI app for downloading metadata in CSV format
    """

    def __init__(self):
        from medin.dws import MedinMetadataRequest
        self.request = MedinMetadataRequest()

    def prepareSOAP(self, environ):
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        areas = get_areas(environ)

        self.gid = gid
        return self.request.prepareCaller(environ['logging.logger'], gid, areas)

    def __call__(self, environ, start_response):
        from cStringIO import StringIO
        from medin.metadata import metadata2csv

        self.prepareSOAP(environ)
        gid = self.gid
        parser = self.request()
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
        metadata2csv(metadata, buf)
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

        self.filters.append(ObfuscateEmails()) # ensure emails are obfuscated when rendered

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

class SOAPRequest(object):
    """
    WSGI Middleware to output SOAP requests for SOAP apps

    A SOAPapp must provide the prepareSOAP() method which must return
    a SOAPCaller object.
    """
    def __init__(self, app):
        self.app = app

    def callerToXML(self, caller):
        return caller.requestXML()

    def isSoapRequest(self, environ):
        try:
            qsl = environ['QUERY_STRING']
        except KeyError:
            return None

        from cgi import parse_qsl

        try:
            soap = dict(parse_qsl(qsl))['soap']
        except KeyError:
            return None

        if soap in ('request', 'response'):
            return soap

        return None

    def __call__(self, environ, start_response):
        soap_type = self.isSoapRequest(environ)
        if not soap_type:
            # delegate to the wrapped app
            return self.app(environ, start_response)

        try:
            caller = self.app.prepareSOAP(environ)
        except AttributeError:
            raise RuntimeError('The wrapped class (%s) does not have the prepareSOAP() method' % self.app.__class__.__name__)

        if soap_type == 'request':
            xml = caller.requestXML()
        else:
            xml = caller.responseXML()

        headers = [('Content-Type', 'application/soap+xml')]

        start_response('200 OK', headers)
        return [xml]

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

        self.filters.append(ObfuscateEmails()) # ensure emails are obfuscated when rendered

    def setup(self, environ):
        title = 'Error - %s' % self.exception.args[0]
        status = self.exception.args[0]
        tvars = dict(message=self.exception.args[1])
        return TemplateContext(title, status=status, tvars=tvars)
