# Introduction

This software has been developed to create the
[MEDIN Portal](http://portal.oceannet.org) by the
[GeoData Institute](http://www.geodata.soton.ac.uk) on behalf of the
[MEDIN partnership](http://www.oceannet.org).

Feedback and input (including code) is welcome. Please email
geodata@soton.ac.uk

# Licence

Unless otherwise indicated by packaged third party code this software
is made available under the Reciprocal Public License (RPL) 1.5. 

You can obtain a full copy of the RPL from
http://opensource.org/licenses/rpl1.5.txt or geodata@soton.ac.uk

# Installation

The server-side software is written for Python 2.7 and is designed to
run on any WSGI or CGI compliant HTTP server. It is recommended that
it be run under CGI for development environments and a persistent WSGI
environment for production deployment (e.g. www.modwsgi.org).

## Getting started using Docker

The easiest way to install the application for production use is to
use [Docker](http://www.docker.io) using the mod wsgi container: after
installing docker running the following command will expose the
application on port `8000`.

    docker run -p=8000:80 homme/medin-portal:wsgi

Port `8000` can be reverse proxied to a public facing web server or
caching service.  Multiple instances of the container could also be
started on separate hosts and connected to a load balancing service.

Even if the docker is not used in production it can be used for
development.  The CGI docker container comes in handy here as the
application is loaded on each request, meaning that changes to the
source files are immediately visible in the application:

    docker run -p=8000:80 homme/medin-portal:cgi

In either case the `Dockerfile`s generating these containers provide
the definitive version of the dependencies and configuration required
by the application and as such should be used as a recipe for
replicating the installation in other environments.  See
`docker/README.md` and the [Docker
Index](https://index.docker.io/u/homme/medin-portal/) for further
details.

## Requirements

The software has the following dependencies:

 * Python 2.7

 * libxml2 >= 2.7 (http://www.xmlsoft.org/) compiled with support for
   Python

 * GDAL >= 1.7 (http://www.gdal.org) compiled with support for OGR

 * TMS/WMS + Python Mapnik 2.0 (http://www.mapnik.org/) compiled with
   support for GDAL + Python

 * sqlite3 (http://www.sqlite.org/) compiled with threadsafe support

 * SQLAlchemy 0.8.4 (http://www.sqlalchemy.org/)

 * rdfextras 0.4 (http://pypi.python.org/pypi/rdfextras/0.4)

 * RDFLib 4.0.1 (http://pypi.python.org/pypi/rdflib/4.0.1)

 * iso8601 0.1.8 (https://pypi.python.org/pypi/iso8601/0.1.8)

 * python-epsg 0.1.4 (https://pypi.python.org/pypi/python-epsg/0.1.4)

 * python-skos 0.0.3 (https://pypi.python.org/pypi/python-skos/0.0.3)

The CGI script is `deploy/portal.cgi` and the WSGI application is
found in `deploy/portal.wsgi`. Your web server should be configured
appropriately to invoke the required script.

In addition, the 'python' directory must be added to the HTTP server's
`PYTHONPATH` location so that the calling python process can locate
the application's modules.

Likewise the contents of the `html` directory should be made available
at the web server's root web location.

## Configuration

The application is configured by setting the `PORTAL_ROOT` environment
variable to the absolute filesystem path of the package's root
directory.

Genetic portal configuration is done by copying the
`etc/portal.ini.example` file to `etc/portal.ini` and editing the
contents as required.

Specific configuration of the portal spatial services is done by
editing the files in the templates/config directory.

Additionally, the online
[EPSG Geodetic Parameter Database](http://epsg-registry.org) should be
updated by running the `bin/epsg-update.py` script when required
(e.g. on a daily basis as a cron job):

    PYTHONPATH=./python python ./bin/epsg-update.py ./data/epsg-registry.sqlite

The above command assumes the script is run from the root distribution
directory: the `PYTHONPATH` variable provides access to the required
packages provided by the distribution.

The vocabulary cache should be updated in a similar way using
`bin/vocab-update.py`. This script uses a newline separated text file
as input to define a number of both local file-based and online
vocabularies. These vocabularies are then cached in a SQLite database
specified as a command line argument along the following lines:

    PYTHONPATH=./python python ./bin/vocab-update.py \
    --vocabularies ./data/vocabularies/vocab-list.txt \
    ./data/vocabularies.sqlite
