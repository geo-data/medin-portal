#!/bin/env python

# ensure the default encoding is utf-8
# see http://blog.ianbicking.org/illusive-setdefaultencoding.html
import sys
sys = reload(sys)
sys.setdefaultencoding('utf-8')

from wsgiref.handlers import CGIHandler
from medin import wsgi_app

CGIHandler().run(wsgi_app())
