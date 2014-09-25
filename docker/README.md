# The Medin Portal under Docker

The `geodata/medin-portal` Docker repository provides three images using the
following tags: `base`; `cgi`; and `wsgi`.  The latter two build on the `base`
image.  The `cgi` image runs the portal as a CGI application; useful for
development scenarios.  The `wsgi` image runs the portal as a mod-wsgi service;
this is intended for production deployment.

As an example, running the following command will deploy the portal on port
`8000` under Apache using mod wsgi:

    docker run -p=8000:80 geodata/medin-portal:wsgi

Port `8000` can be reverse proxied to a public facing web server or
caching service.  Multiple instances of the container could also be
started on separate hosts and connected to a load balancing service.

Even if the docker is not used in production it can be used for
development.  The CGI docker container comes in handy here as the
application is loaded on each request, meaning that changes to the
source files are immediately visible in the application:

    docker run -p=8000:80 geodata/medin-portal:cgi

It is sensible for performance reasons to persist the tile cache data and
compiled templates on the host system.  Not doing this forces the tile cache to
be regenerated each time the Docker server is restarted.  The following command
will persist on the host system under `/data/medin-portal`:

    docker run --rm -p 8000:80 -v /data/medin-portal:/tmp homme/medin-portal:wsgi

The Docker images are available at the [Docker Index](https://index.docker.io/).
These images are automatically updated to reflect changes in the source code
repository on GitHub .

The images can also be built locally along the following lines from the root of
the source checkout:

    docker build -t geodata/medin-portal:base ./docker/base
    docker build -t geodata/medin-portal:cgi ./docker/cgi
    docker build -t geodata/medin-portal:wsgi ./docker/wsgi

See the [GitHub repository](https://github.com/geo-data/medin-portal) for
further details.
