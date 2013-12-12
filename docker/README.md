# Medin Portal on Docker

[Docker](http://www.docker.io/) provides a Linux environment for
applications to run in containers.  This directory tree provides the
files necessary to create docker images (containers) which run the
Medin Portal.

Three docker images are created: `base`; `cgi`; and `wsgi`.  The
latter two build on the `base` image.  The `cgi` image runs the portal
as a CGI application; useful for development scenarios.  The `wsgi`
image runs the portal as a mod-wsgi service; this is intended for
production deployment. These can be created using docker commands long
the following lines:

    docker build -t homme/medin-portal:base ./base
    docker build -t homme/medin-portal:cgi ./cgi
    docker build -t homme/medin-portal:wsgi ./wsgi

Pre-generated images corresponding to these commands can be found in
the [Docker Index](https://index.docker.io/).

As an example the following command runs the mod wsgi container,
exposing the application on port `8000` of the host machine:

    docker run -p=8000:80 homme/medin-portal:wsgi
