##
# Medin Portal under mod wsgi
#
# This builds on the Medin Portal base image to configure Apache to
# run the Medin Portal under mod-wsgi.  This is intended for
# production deployment.
#

FROM homme/medin-portal:base

MAINTAINER Homme Zwaagstra <hrz@geodata.soton.ac.uk>

# Install mod-wsgi
RUN apt-get install -y libapache2-mod-wsgi

# Set up the mod-wsgi based virtual host
ADD apache-vhost.conf /etc/apache2/sites-available/medin-portal
RUN ln -s /etc/apache2/sites-available/medin-portal /etc/apache2/sites-enabled/000-medin-portal
RUN rm /etc/apache2/sites-enabled/000-default

# Link in the portal WSGI implementation to the web server
RUN mkdir /var/medin-portal/wsgi && ln -s /usr/src/medin-portal/deploy/search.wsgi /var/medin-portal/wsgi/search.wsgi

# Start Apache by default
CMD chmod a+rwxt /tmp && service apache2 start && tail -F /var/log/apache2/error.log
