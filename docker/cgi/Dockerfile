##
# Medin Portal under CGI
#
# This builds on the Medin Portal base image to configure Apache to
# run the Medin Portal under CGI.  This is useful for development
# deployment.
#

FROM homme/medin-portal:base

MAINTAINER Homme Zwaagstra <hrz@geodata.soton.ac.uk>

# Set up the CGI based virtual host
ADD apache-vhost.conf /etc/apache2/sites-available/medin-portal
RUN ln -s /etc/apache2/sites-available/medin-portal /etc/apache2/sites-enabled/000-medin-portal
RUN rm /etc/apache2/sites-enabled/000-default

# Start Apache by default
CMD service apache2 start && tail -F /var/log/apache2/error.log
