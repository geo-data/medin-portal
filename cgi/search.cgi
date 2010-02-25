#!/bin/env python

from wsgiref.handlers import CGIHandler
from medin import wsgi_app

CGIHandler().run(wsgi_app())
