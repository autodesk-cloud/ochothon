FROM autodeskcloud/pod:1.0.6

#
# - add pyyaml
#
RUN pip install pyyaml

#
# - add our internal toolset package
# - install it
#
ADD resources/toolset /opt/python/toolset
RUN cd /opt/python/toolset && python setup.py install

#
# - add our spiffy pod script + the portal code itself
# - add the web-shell templates
# - add our supervisor script
# - start supervisor
#
ADD resources/pod /opt/portal/pod
ADD resources/portal.py /opt/portal/
ADD resources/templates /opt/portal/templates
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf