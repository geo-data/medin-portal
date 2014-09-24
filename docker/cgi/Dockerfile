##
# Medin Portal under CGI
#
# This builds on the Medin Portal base image to configure Apache to
# run the Medin Portal under CGI.  This is useful for development
# deployment.
#

FROM geodata/medin-portal:base

MAINTAINER Homme Zwaagstra <hrz@geodata.soton.ac.uk>

# Set up the CGI based virtual host
ADD apache-vhost.conf /etc/apache2/sites-available/medin-portal.conf
RUN a2dissite 000-default
RUN a2ensite medin-portal

# Start Apache by default
CMD chmod a+rwxt /tmp && service apache2 start && tail -F /var/log/apache2/error.log
