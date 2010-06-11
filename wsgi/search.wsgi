# ensure the default encoding is utf-8
# see http://blog.ianbicking.org/illusive-setdefaultencoding.html
import sys
sys = reload(sys)
sys.setdefaultencoding('utf-8')

from medin import wsgi_app

application = wsgi_app()

if __name__ == '__main__':
    from wsgiref.simple_server import make_server

    httpd = make_server('', 8100, application)
    print "Serving HTTP on port 8100..."

    # Respond to requests until process is killed
    httpd.serve_forever()
