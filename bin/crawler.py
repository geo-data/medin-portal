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
__version__ = 0.1

import libxml2
import urllib2
from urlparse import urlparse

class Crawler(object):
    """
    An object for crawling and testing web pages.

    Instances of this class are designed to visit an URL and report
    back on any technical problems with it. If the URL is advertised
    as being a form of XML by the HTTP Content-Type header then it is
    parsed. Any URIs contained in 'src' or 'href' attributes are
    extracted and crawled in a similar way.
    """
    
    restrict = None
    exclude = None

    def __init__(self, restrict=None, exclude=None):
        if restrict: self.restrict = set(restrict)
        if exclude: self.exclude = set(exclude)
        self.parser = libxml2.newParserCtxt()             
        self.opener = urllib2.build_opener()
        self.opener.addheaders = [('User-agent', "Homme's Web Tester (v%s)" % str(__version__))] # User Agent string
        self.visited = set()

    def clear(self):
        """
        Clear the cache of previously visited links.
        """
        
        self.visited.clear()

    def _handleXMLError(self, arg, msg, severity, reserved):
        """
        Handle XML parsing errors.

        This is not used at the moment, but could in future be set on
        the libxml2 parser using self.parser.setErrorHandler().
        """
        
        print arg, msg, severity, reserved

    def isXML(self, content_type):
        """
        Return True if the content type is XML based.
        """
        
        if content_type in ('text/html', 'application/xml'):
            return True
        elif content_type.startswith('application/') and content_type.endswith('+xml'):
            return True

        return False

    def isRestricted(self, url):
        """
        Check whether the URL is restricted.

        Restricted URLs are those which fall under valid URL space and
        should be visited.
        """
        
        if not self.restrict:
            return False
        
        for restricted in self.restrict:
            if url.startswith(restricted):
                return True

        return False

    def isExcluded(self, url):
        """
        Check whether the URL is excluded.

        Excluded URLs are not visited.
        """
        
        if not self.exclude:
            return False
        
        for excluded in self.exclude:
            if url.startswith(exclude):
                return True

        return False

    def isURLInvalid(self, url):
        """
        Check the validity of an URL.

        Returns an error message if the parsed URI is invalid in any
        way, None otherwise.
        """

        urlstr = url.geturl()
        if url.scheme and url.scheme not in ('http', 'https', 'ftp', 'ftps'):
            return 'Unsupported scheme: %s' % url.scheme # it's a mailto:, javascript: etc.
        elif not url.scheme or not url.netloc:
            return 'No URI scheme or domain location'
        
        if urlstr in self.visited:
            return 'Previously visited URI'
        
        if not self.isRestricted(urlstr):
            return 'External URI'

        if self.isExcluded(urlstr):
            return 'Excluded URI'

        return None

    def crawlParsedURL(self, url):
        """
        Crawl a parsed URL, returning a count of visited links

        The url parameter is the value returned by urlparse.urlparse()
        """

        # check whether the URL is valid
        urlstr = url.geturl()
        error = self.isURLInvalid(url)
        if error:
            print "Not crawling %s: %s" % (urlstr, error)
            return 0

        # flag the URL has having been visited
        print "Crawling %s" % urlstr
        self.visited.add(urlstr)

        # open the URL
        try:
            r = self.opener.open(urlstr)
        except urllib2.HTTPError, e:
            print e
            return 1

        # deal with re-directs
        if urlstr != r.url:
            url = urlparse(r.url)
            urlstr = r.url
            error = self.isURLInvalid(url)
            if error:
                print "Redirected to invalid URI (%s): %s" % (urlstr, error)
                return 1
            else:
                print "Redirected to: %s" % urlstr
                self.visited.add(urlstr)

        # check to see whether we are dealing with XML
        info = r.info()
        if not self.isXML(info.gettype()):
            return 1

        # get the XML content
        content = r.read()
        if not content:
            return 1

        # parse into an XML DOM
        doc = self.parser.ctxtReadMemory(content, len(content), urlstr, 'utf-8',
                                         libxml2.PARSER_VALIDATE | libxml2.PARSER_SUBST_ENTITIES)
        if not doc:
            return 1

        # extract all resource links
        links = set()
        for node in doc.xpathEval2('//@href | //@src'):
            link = node.content
            parsed = urlparse(link)

            if not parsed.scheme and not parsed.netloc:
                # replace with base url values
                kwargs = dict(netloc=url.netloc, scheme=url.scheme)

                # see whether it's a relative URL that needs to be fully qualified
                if parsed.path.startswith('../'):
                    base = url.path.rstrip('/').rsplit('/', 1)[0]
                    kwargs['path'] = '/'.join((base, parsed.path[3:]))
                elif not parsed.path.startswith('/'):
                    kwargs['path'] = '/'.join((url.path.rstrip('/'), parsed.path))
                    
                parsed = parsed._replace(**kwargs)

            links.add(parsed)

        # crawl all extracted links
        count = 1
        for link in links:
            count += self.crawlParsedURL(link)

        return count

    def crawl(self, url):
        """
        Crawl a parsed URL, returning a count of visited links
        """

        frags = urlparse(url)
        return self.crawlParsedURL(frags)

def main():
    """
    Create a crawler program.
    """
    
    try:
        import sys

        url = sys.argv[1]

        crawler = Crawler([url])
        crawler.crawl(url)
    except KeyboardInterrupt:
        print "\nInterrupted!"
        
if __name__ == '__main__':
    main()
