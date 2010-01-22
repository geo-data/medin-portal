# System modules
import os

from errata import HTTPError

# Utility Classes

class MakoApp(object):
    """Base class creating WSGI application for rendering Mako templates"""

    def __init__(self, path, expand=True):
        self.path = path
        self.expand = expand

    def setup(self, environ):
        return TemplateContext('')

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""
        
        template = self.get_template(environ, self.path, self.expand)

        ctxt = self.setup(environ)
        
        kwargs = self.get_template_vars(environ, ctxt.title)
        kwargs.update(ctxt.tvars)
    
        output = template.render(**kwargs)

        start_response(ctxt.status, ctxt.headers)
        return [output]

    def get_template(self, environ, path, expand=True):
        def template_lookup(environ):
            try:
                return MakoApp._template_lookup
            except AttributeError:
                pass

            def get_template_dir(environ):
                try:
                    return MakoApp._template_dir
                except AttributeError:
                    pass

                try:
                    doc_root = environ['DOCUMENT_ROOT']
                except KeyError:
                    raise EnvironmentError('The DOCUMENT_ROOT environment variable is not available')

                template_dir = os.path.join(os.path.dirname(doc_root), 'templates')
                if not os.path.exists(template_dir):
                    raise RuntimeError('The template directory does not exist: %s' % template_dir)

                MakoApp._template_dir = template_dir
                return template_dir

            from mako.lookup import TemplateLookup

            template_dir = get_template_dir(environ)
            _template_lookup = TemplateLookup(directories=[template_dir],
                                              input_encoding='utf-8',
                                              output_encoding='utf-8',
                                              filesystem_checks=False)

            MakoApp._template_lookup = _template_lookup
            return _template_lookup
        
        lookup = template_lookup(environ)
        path = os.path.join(os.path.sep, *path)
        if expand:
            try:
                template = environ['selector.vars']['template'] # the template
            except KeyError:
                try:
                    # try and get the template as the first path entry
                    template = environ['PATH_INFO'].split('/')[1]
                except KeyError, IndexError:
                    raise RuntimeError('No template is specified')
                
            path = path % template
        return lookup.get_template(path)

    def get_template_vars(self, environ, title, **kwargs):
        def get_http_root(environ):
            return '%s://%s' % (environ['wsgi.url_scheme'], environ['HTTP_HOST'])

        def get_script_root(environ):
            return ''.join((get_http_root(environ), environ['SCRIPT_NAME']))

        def get_resource_root(environ):
            try:
                return get_script_root(environ) + environ['PATH_INFO']
            except KeyError:
                 return get_script_root(environ)
        
        vars = dict(title=title,
                    request_uri=environ['REQUEST_URI'],
                    http_root=get_http_root(environ),
                    script_root=get_script_root(environ),
                    resource_root=get_resource_root(environ),
                    environ=environ)

        # Add some useful environment variables to the template
        for k in ('REQUEST_URI', 'QUERY_STRING'):
            kl = k.lower()
            try:
                vars[kl] = environ[k]
            except KeyError:
                vars[kl] = environ['']

        if vars['query_string']: vars['query_string'] = '?' +  vars['query_string']

        # combine the kwargs and vars, overriding vars keys with
        # kwargs if present
        vars.update(kwargs)
        return vars

class TemplateContext(object):
    def __init__(self, title, headers=None, tvars=None, status='200 OK'):
        self.status = status
        if headers is None:
            headers = [('Content-type', 'text/html')]
        self.headers = headers
        self.title = title
        if tvars is None:
            tvars = {}
        self.tvars = tvars

# The WSGI Applications

class OpenSearch(MakoApp):
    def __init__(self):
        super(OpenSearch, self).__init__(['opensearch', 'catalogue', '%s.xml'])

    def setup(self, environ):
        title = 'MEDIN Catalogue'
        headers = [('Content-type', 'application/opensearchdescription+xml')]
        return TemplateContext(title, headers=headers)

class Search(MakoApp):
    def __init__(self):
        super(Search, self).__init__(['%s', 'search.html'])

    def setup(self, environ):
        return TemplateContext('Search')

class Results(MakoApp):
    def __init__(self):
        super(Results, self).__init__(['%s', 'catalogue.html'])

    def setup(self, environ):
        from medin.dws import SearchQuery, Search, DWSError

        try:
            qsl = environ['QUERY_STRING']
        except KeyError:
            qsl = ''

        q = SearchQuery(qsl)
        try:
            req = Search()
        except DWSError:
            raise HTTPError('500 Internal Server Error', dws.args[0])

        r = req(q)
        results = []
        for id, title in r.results:
            results.append(dict(id=id, title=title))

        tvars=dict(hits=r.hits,
                   start_index = r.start_index,
                   end_index = r.end_index,
                   count = r.count,
                   results=results)
            
        return TemplateContext('Catalogue Results', tvars=tvars)

class Metadata(MakoApp):
    def __init__(self):
        super(Metadata, self).__init__(['%s', 'metadata.html'])

    def setup(self, environ):
        gid = environ['selector.vars']['gid'] # the global metadata identifier
        title = 'Metadata %s' % gid
        tvars = dict(gid=gid)

        return TemplateContext(title, tvars=tvars)

class TemplateChoice(MakoApp):
    def __init__(self):
        super(TemplateChoice, self).__init__(['light', 'templates.html'], False)

    def setup(self, environ):
        return TemplateContext('Choose Your Search Format')
