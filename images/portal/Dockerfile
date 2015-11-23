FROM autodeskcloud/pod:1.0.7

#
# - add dnsutils (to get dig)
# - add pyyaml
#
RUN apt-get -y update && apt-get -y install dnsutils
RUN pip install pyyaml

#
# - add our internal toolset package
# - install it
#
ADD resources/toolset /opt/python/toolset
RUN cd /opt/python/toolset && python setup.py install

#
# - add our spiffy pod script + the portal code itself
# - add our supervisor script
# - start supervisor
#
ADD resources/pod /opt/portal/pod
ADD resources/portal.py /opt/portal/
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf