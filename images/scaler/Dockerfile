FROM lmok/pod

#
# - add pip, pyyaml & redis
#
RUN apt-get update && apt-get -y install python-pip vim
RUN pip install --no-use-wheel --upgrade distribute
RUN pip install redis pyyaml

#
# - add our internal toolset package
# - install it
#
ADD resources/toolset /opt/scaler/toolset

#
# - add our spiffy pod script + the scaler code itself
# - add our supervisor script
# - start supervisor
#
ADD resources/pod /opt/scaler/pod
ADD resources/scaler.py /opt/scaler/
ADD resources/supervisor /etc/supervisor/conf.d
CMD /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf