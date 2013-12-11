##
# Medin Portal Base Image
#
# This creates an Ubuntu derived base image that installs the latest
# tagged version of the Medin Portal code along with the relevant
# dependencies.  The environment includes an Apache 2 setup that is
# ready configuring by derived images.
#

FROM ubuntu:quantal

MAINTAINER Homme Zwaagstra <hrz@geodata.soton.ac.uk>

# Ensure the package repository is up to date
RUN echo "deb http://archive.ubuntu.com/ubuntu quantal main universe" > /etc/apt/sources.list
RUN apt-get update

# Install dependencies provided by Ubuntu repositories
RUN apt-get install -y git apache2 python-libxml2 python-gdal python-mapnik2 python-pip libapache2-mod-xsendfile

# Install dependencies provided by PIP
RUN pip install SQLAlchemy==0.8.4 iso8601==0.1.8 rdfextras==0.4 rdflib==4.0.1

# The epsg module needs to be installed separately to SQLAlchemy to avoid problems
RUN pip install python-epsg==0.1.3 python-skos==0.0.3

# Clone the git repository
RUN git clone https://github.com/geo-data/medin-portal.git /usr/src/medin-portal
RUN cd /usr/src/medin-portal && git checkout docker
RUN cd /usr/src/medin-portal && git submodule init && git submodule update

# Set up the web root and link in the relevant static portal files
RUN mkdir -p /var/medin-portal/html
RUN ln -s /usr/src/medin-portal/html/* /var/medin-portal/html/
RUN ln -s /usr/src/medin-portal/templates /var/medin-portal/templates
RUN ln -s /usr/src/medin-portal/data /var/medin-portal/data

# Set up a temporary directory not under union fs control
VOLUME ["/tmp"]
RUN chmod a+rwxt /tmp
RUN ln -s /tmp /var/medin-portal/tmp

# Install the portal configuration file
RUN mkdir /var/medin-portal/etc 
RUN cp /usr/src/medin-portal/etc/portal.ini.example /var/medin-portal/etc/portal.ini

# Set up the custom Apache log directory
RUN mkdir /var/medin-portal/logs && chown nobody /var/medin-portal/logs

# Update the SKOS based vocabulary cache
RUN cd /usr/src/medin-portal && PYTHONPATH=./python python ./bin/vocab-update.py  --vocabularies ./data/vocabularies/vocab-list.txt ./data/vocabularies.sqlite
