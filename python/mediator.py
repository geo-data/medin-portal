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

class Mediator:
    """WSGI middleware preprocessor which delegates to subsequent WSGI
    apps based on the media type as specified in the request 'Accept'
    header.
    """

    def __init__(self, media_handlers = {}):
        self.media_handlers = {}
        for media_type, handler in media_handlers.items():
            self.add(media_type, handler)       

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""
        
        if not self.media_handlers:
            raise LookupError('At least one media handler must be specified')

        # get the Accept header, specifying a default of any media type if none is found
        try:
            accept_header = environ['HTTP_ACCEPT']
        except KeyError:
            accept_header = '*/*'

        # we now need a handler for a media type acceptable to the client
        media_types = self.acceptableToClient(accept_header)
        media_handler = self.getMediaHandler(media_types)
        if media_handler is not None:
            media_type, handler = media_handler

            # wrap start_response() to perform a sanity check on the response content-type
            def check_response(status, headers):
                content_count = 0
                for (header, value) in headers:
                    if header.lower() != 'content-type':
                        continue
                    
                    content_count += 1
                    value = value.split(';')[0] # we only need the content-type
                    if value != media_type and media_type != '*/*':
                        (returned_type, returned_subtype) = value.split('/')
                        if returned_subtype == '*':
                            expected_type = media_type.split('/')[0]
                            if expected_type == returned_type:
                                continue

                        raise RuntimeError('Response Content-type (%s) does not match expected content type (%s)' % (value, media_type))
                            
                if content_count == 0:
                    raise RuntimeError('No Content-type has been set: expected Content-type %s' % media_type)
                            
                start_response(status, headers)
            
            return handler(environ, check_response)
        else:
            response_types = ','.join(self.acceptableToServer())
            start_response("406 Not Acceptable", [('Content-type', 'text/plain')])
            return ["Only the following media types are accepted: %s" % response_types]

    def add(self, media_type, handler):
        (mtype, msubtype) = media_type.split('/')
        try:
            self.media_handlers[mtype][msubtype] = handler # add to existing type
        except KeyError:
            self.media_handlers[mtype] = {msubtype: handler} # initialise type

    def getMediaHandler(self, media_types):
        # iterate through the media types and try to find a handler for one of them
        for (media_type, params) in media_types:
            (mtype, msubtype) = media_type.split('/')

            # try to return the specific handler
            try:
                return ('%s/%s' % (mtype, msubtype), self.media_handlers[mtype][msubtype])
            except KeyError:
                pass

            # try to return a handler for an unspecified subtype of the specified type
            if msubtype == '*':
                try:
                    msubtype = self.media_handlers[mtype].iterkeys().next()
                    return ('%s/%s' % (mtype, msubtype), self.media_handlers[mtype][msubtype])
                except KeyError:
                    pass
            
            # return any handler if that's what is required
            if media_type == '*/*':
                mtype = self.media_handlers.iterkeys().next()
                msubtype = self.media_handlers[mtype].iterkeys().next()
                return ('%s/%s' % (mtype, msubtype), self.media_handlers[mtype][msubtype])

        return None

    def acceptableToServer(self):
        types = []
        for mtype in self.media_handlers.keys():
            if mtype != '*':
                for msubtype in self.media_handlers[mtype]:
                    types.append('%s/%s' % (mtype, msubtype))
        return types        

    def acceptableToClient(self, accept):
        """
        Returns a list of media types acceptable to the client

        The list is comprised of two element tuples containing the
        media type and a dictionary of parameters. The list is ordered
        such that preferred media types are at the beginning of the
        list.
        """

        # create a list of media types
        media_types = []
        for media_range in accept.split(','):
            values = media_range.split(';')
            media_type = values.pop(0).strip()

            # extract any parameters from the media type
            params = {}
            for param in values:
                param = param.split('=')
                key = param.pop(0)
                try:
                    params[key] = param[0]
                except IndexError:
                    params[key] = None

            # assign a q-number to the media_type
            try:
                q = string.atof(params.pop('q'))
            except:
                q = 1

            # add the media type data and sorting parameters to the list
            media_types.append(((media_type, params), q, len(params)))

        # sort the list based firstly on q-number and secondly on specificity of parameters
        media_types.sort(lambda x, y: (-cmp(x[1], y[1]) or -cmp(x[2], y[2])))

        # we only want to return media type data, not the sorting parameters
        return [media_type[0] for media_type in media_types]
