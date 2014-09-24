# Medin Portal on Docker

The `geodata/medin-portal` repository provides three images using the following
tags: `base`; `cgi`; and `wsgi`.  The latter two build on the `base` image.  The
`cgi` image runs the portal as a CGI application; useful for development
scenarios.  The `wsgi` image runs the portal as a mod-wsgi service; this is
intended for production deployment. These can be created using docker commands
long the following lines from the root of the source checkout:

    docker build -t geodata/medin-portal:base ./docker/base
    docker build -t geodata/medin-portal:cgi ./docker/cgi
    docker build -t geodata/medin-portal:wsgi ./docker/wsgi

Pre-generated images corresponding to these commands can be found in
the [Docker Index](https://index.docker.io/).

As an example the following command runs the mod wsgi container,
exposing the application on port `8000` of the host machine:

    docker run -p=8000:80 geodata/medin-portal:wsgi

See the [GitHub repository](https://github.com/geo-data/medin-portal) for
further details.
