FROM paugamo/pod

#
# - add pip, pyyaml & reds
#
RUN apt-get update && apt-get -y install wget python-pip
RUN pip install --no-use-wheel --upgrade distribute
RUN pip install redis pyyaml

#
# - add our internal toolset package
# - install it
#
ADD resources/toolset /opt/toolset
RUN cd /opt/toolset && python setup.py install

#
# - add the web-shell templates
#
ADD resources/templates /opt/portal/templates

#
# - add our spiffy pod script + the portal code itself
# - add our supervisor script
# - start supervisor
#
ADD resources/pod /opt/portal/pod
ADD resources/portal.py /opt/portal/
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf