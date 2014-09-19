##
# Medin Portal under mod wsgi
#
# This builds on the Medin Portal base image to configure Apache to
# run the Medin Portal under mod-wsgi.  This is intended for
# production deployment.
#

# Ubuntu Trusty
FROM ubuntu:14.04

MAINTAINER Homme Zwaagstra <hrz@geodata.soton.ac.uk>

# Ensure the package repository is up to date
RUN apt-get update

# Install dependencies provided by Ubuntu repositories
RUN apt-get install -y git apache2 python-libxml2 python-gdal python-mapnik2 python-pip libapache2-mod-xsendfile libapache2-mod-wsgi python-dev

# Install dependencies provided by PIP
RUN pip install SQLAlchemy==0.9.7 iso8601==0.1.10 rdfextras==0.4 rdflib==4.1.2

# The epsg module needs to be installed separately to SQLAlchemy to avoid problems
RUN pip install python-epsg==0.1.4 python-skos==0.1.1

# Clone the git repository
RUN git clone https://github.com/geo-data/medin-portal.git /usr/src/medin-portal
RUN cd /usr/src/medin-portal && git checkout live-docker
RUN cd /usr/src/medin-portal && git submodule init && git submodule update

# Update the EPSG registry cache. This may take a while...
RUN cd /usr/src/medin-portal && PYTHONPATH=./python python ./bin/epsg-update.py ./data/epsg-registry.sqlite

# Update the SKOS based vocabulary cache
RUN cd /usr/src/medin-portal && PYTHONPATH=./python python ./bin/vocab-update.py  --vocabularies ./data/vocabularies/vocab-list.txt ./data/vocabularies.sqlite

# Set up the web root and link in the relevant static portal files.
RUN mkdir -p /var/medin-portal/html
RUN ln -s /usr/src/medin-portal/html/* /var/medin-portal/html/
RUN ln -s /usr/src/medin-portal/templates /var/medin-portal/templates
# The data directory has to be hard linked rather than symlinked so
# that relative links within `data/raster/background-wms.vrt` work
# correctly.
RUN cp --archive --link /usr/src/medin-portal/data /var/medin-portal/data

# Set up a temporary directory not under union fs control
VOLUME ["/tmp"]
#RUN chmod a+rwxt /tmp # This doesn't seem to work
RUN ln -s /tmp /var/medin-portal/tmp

# Install the portal configuration file. This includes setting the
# `local_port` variable.
RUN mkdir /var/medin-portal/etc 
RUN sed -e 's/;local_port/local_port/g' /usr/src/medin-portal/etc/portal.ini.example > /var/medin-portal/etc/portal.ini

# Set up the mod-wsgi based virtual host
ADD apache-vhost.conf /etc/apache2/sites-available/medin-portal.conf
RUN a2dissite 000-default
RUN a2ensite medin-portal

# Link in the portal WSGI implementation to the web server
RUN mkdir /var/medin-portal/wsgi && ln -s /usr/src/medin-portal/deploy/search.wsgi /var/medin-portal/wsgi/search.wsgi

# Expose the HTTP port
EXPOSE 80

# Start Apache by default
CMD chmod a+rwxt /tmp && service apache2 start && tail -F /var/log/apache2/error.log
