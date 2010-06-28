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

# System modules
import os

def get_template_name(environ):
    """
    Extract the template name from the environment
    """
    try:
        template = environ['selector.vars']['template'] # the template
    except KeyError:
        try:
            # try and get the template as the first path entry
            template = environ.get('PATH_INFO', '').split('/')[1]
        except KeyError, IndexError:
            return None

    return template

def set_template_name(environ, template):
    """
    Add the template name to the environment

    Returns any previous template setting
    """
    try:
        previous = environ['selector.vars']['template']
        environ['selector.vars']['template'] = template
    except KeyError:
        previous = None
        environ['selector.vars'] = {'template': template}

    return previous

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

    def __init__(self, path, expand=True, check_etag=True, content_type=None):
        self.path = path
        self.expand = expand
        self.check_etag = check_etag
        self.content_type = content_type

    def setup(self, environ):
        return TemplateContext('')

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""

        headers = []
        # check whether the etag is valid
        if self.check_etag:
            from medin.views import check_etag
            etag = check_etag(environ, ''.join(self.path))
            headers.append(('Etag', etag))
        if self.content_type:
            headers.append(('Content-Type', self.content_type+';charset=utf-8'))
        
        template = self.get_template(environ, self.path, self.expand)

        ctxt = self.setup(environ)
        ctxt.headers.extend(headers)    # add the etag
        
        kwargs = self.get_template_vars(environ, ctxt.title)
        kwargs.update(ctxt.tvars)
    
        output = template.render(**kwargs)

        start_response(ctxt.status, ctxt.headers)
        return [output]

    def get_template(self, environ, path, expand=True):
        template_lookup = TemplateLookup(environ)
        lookup = template_lookup.lookup()
        path = os.path.join(os.path.sep, *path)
        if expand:
            template = get_template_name(environ)
            if template is None:
                raise RuntimeError('No template is specified')
            path = path % template
        return lookup.get_template(path)

    def get_template_vars(self, environ, title, **kwargs):
        from medin import __version__ as version
        from datetime import date

        if self.content_type:
            content_type = self.content_type
        else:
            try:
                content_type = environ['portal.content-type']
            except KeyError:
                raise RuntimeError('No content-type is specified')
        
        vars = dict(title=title,
                    request_uri=environ.request_uri(),
                    http_root=environ.http_uri(),
                    script_root=environ.script_uri(),
                    resource_root=environ.resource_uri(),
                    content_type=content_type,
                    notices=environ['logging.handler'].notices(),
                    warnings=environ['logging.handler'].warnings(),
                    errors=environ['logging.handler'].errors(),
                    version=version,
                    year=date.today().year,
                    runtime=environ['portal.timer'].runtime(),
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
            # always check validation and always obey freshness information
            headers = [('Cache-Control', 'no-cache, must-revalidate')] 
        self.headers = headers
        self.title = title
        if tvars is None:
            tvars = {}
        self.tvars = tvars
