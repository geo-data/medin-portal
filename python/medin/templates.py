# System modules
import os

class TemplateLookup(object):

    def __init__(self, environ):
        try:
            self.template_dir = self.__class__._template_dir
            self.module_dir = self.__class__._module_dir
            return
        except AttributeError:
            pass
        
        self.template_dir = self.__class__._template_dir = os.path.join(environ.root, 'templates')
        self.module_dir = self.__class__._module_dir = os.path.join(environ.root, 'tmp')
        if not os.path.exists(self.template_dir):
            raise RuntimeError('The template directory does not exist: %s' % self.template_dir)

    def lookup(self):
        try:
            return self.__class_._template_lookup
        except AttributeError:
            pass

        from mako.lookup import TemplateLookup

        self.__class__._template_lookup = TemplateLookup(directories=[self.template_dir],
                                                         input_encoding='utf-8',
                                                         output_encoding='utf-8',
                                                         filesystem_checks=False,
                                                         module_directory=self.module_dir)
        return self.__class__._template_lookup
    
class MakoApp(object):
    """Base class creating WSGI application for rendering Mako templates"""

    def __init__(self, path, expand=True, check_etag=True):
        self.path = path
        self.expand = expand
        self.check_etag = check_etag

    def setup(self, environ):
        return TemplateContext('')

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""

        headers = []
        # check whether the etag is valid
        if self.check_etag:
            from medin import check_etag
            etag = check_etag(environ, ''.join(self.path))
            headers.append(('Etag', etag))
        
        template = self.get_template(environ, self.path, self.expand)

        ctxt = self.setup(environ)
        ctxt.headers.extend(headers)    # add the etag
        
        kwargs = self.get_template_vars(environ, ctxt.title)
        kwargs.update(ctxt.tvars)
    
        output = template.render(**kwargs)

        start_response(ctxt.status, ctxt.headers)
        return [output]

    def get_template_name(self, environ):
        try:
            template = environ['selector.vars']['template'] # the template
        except KeyError:
            try:
                # try and get the template as the first path entry
                template = environ.get('PATH_INFO', '').split('/')[1]
            except KeyError, IndexError:
                raise RuntimeError('No template is specified')

        return template

    def get_template(self, environ, path, expand=True):
        template_lookup = TemplateLookup(environ)
        lookup = template_lookup.lookup()
        path = os.path.join(os.path.sep, *path)
        if expand:
            template = self.get_template_name(environ)
            path = path % template
        return lookup.get_template(path)

    def get_template_vars(self, environ, title, **kwargs):
        from medin import __version__ as version
        from datetime import date
        
        vars = dict(title=title,
                    request_uri=environ.request_uri(),
                    http_root=environ.http_uri(),
                    script_root=environ.script_uri(),
                    resource_root=environ.resource_uri(),
                    log=environ['logging.handler'].records(),
                    version=version,
                    year=date.today().year,
                    environ=environ)

        # Add some useful environment variables to the template
        for k in ['QUERY_STRING']:
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
