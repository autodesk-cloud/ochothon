Tools
=====

The tool set
____________

Overview
********

The *portal* application we run as a proxy embeds a whole bunch of tools. Those are all little standalone Python_
scripts that the *portal* will *POpen()* from a temporary directory. They all support a *--help* switch which displays
detailed information, supported parameters and so on.

You can also use the **help** command to print out a complete list of tools.

Container definitions
*********************

In order to deploy our Ochopod_ clusters we need to feed enough information to Marathon_ and deploy specific
constructs (*applications* in the present case). This is all done by the **deploy** tool in a fairly generic fashion.

Now we of course want to pass just enough data to quantify what we need to run, what ports to expose and so on. This
is done via a tiny YAML_ file I call a *container definition*. For instance:

.. code:: yaml

    cluster:  zookeeper
    image:    paugamo/marathon-ec2-zookeeper
    ports:
        - 2181
        - 2888
        - 3888

.. note::

    This YAML_ file is **not** related to the Marathon_ API in any way. This is completely specific to Ochopod_.

This little snippet can be uploaded and passed to the **deploy** tool which will then turn it into a full-fledged
*application* call to the Marathon_ API. Any required setting for Ochopod_ will be added in there as well transparently.

.. note::

    Please note I decided to split image building & deployment as it turned out to be impractical to have the *portal*
    to build/push images on its own. With the current model you are assumed to have images already built somewhere,
    which is still fine.

Debug logging
*************

You can always get access to your Ochopod_ internal log (located at */var/log/ochopod.log*) for all your containers.
Simply use the **log** tool for that. Now the log level is by default set to *INFO* and above. You can force it to
*DEBUG* by switching the optional *debug* setting to true. For instance:

.. code:: yaml

    cluster:  zookeeper
    image:    paugamo/marathon-ec2-zookeeper
    debug:    true
    ports:
        - 2181
        - 2888
        - 3888

This can be helpful to troubleshoot problems at runtime. Beware, the Ochopod_ debug log is quite verbose.

Container settings
******************

The optional *settings* block which can hold arbitrary nested data. This will be turned into a single serialized
JSON snippet and passed to the container as the *$pod* environment variable. Very handy to specify complex runtime
settings. For instance:

.. code:: yaml

    settings:
        jvm-options:
          -Xms1g
          -Xmx2g

You also have the ability to override those settings when using the **deploy** tool. Simply use the *-o* command line
option and point to a local YAML_ file. This file simply maps arbitrary settings for a given fully qualified cluster
identifier. For instance:

.. code:: yaml

    dev.web-server:
        debug: true
        jvm-options:
          -Xmx1g

    prod.web-server:
        debug: false
        jvm-options:
          -Xmx4g

Any container from cluster *web-server* under namespace *dev* will thus see *debug* set to true in its *$pod* variable.

Port mappings
*************

You can define the TCP ports you wish to expose via the lightweight *ports* array setting. Each port binding can be
either an integer (default case mapping this port to some random port on the underlying node), two integers (the first
one being the container port and the second the corresponding port on the host) or an integer followed by a * (same
as before except both ports are the same). This will be mapped to the syntax Marathon_ expects. For instance:

.. code:: yaml

    ports:
        - 3000
        - 5000 *
        - 9000 9001

Verbatim settings
*****************

You can customize your *container definition* even further by adding optional *verbatim* settings. Those will be
included as is when making the REST call to the Marathon_ masters. This is especially useful for idiosyncrasies such
as the resource quotas. For instance:

.. code:: yaml

    cluster:  zookeeper
    image:    paugamo/k8s-ec2-zookeeper
    settings:
    verbatim:
        cpu: 1.0
        mem: 256
        
    ports:
        - 2181
        - 2888
        - 3888

Your clusters
*************

Once a Ochopod_ cluster is deployed you will get a new *application* (plus a certain number of *tasks*). Its
name will be assembled from the Ochopod_ cluster & namespace plus a unique timestamp. You don't have to worry about
how this is done, what the Marathon_ API looks like and so on.

The **deploy** command allows you to spawn new containers by creating a new (uniquely named) Marathon_ application.
These containers will form (or join) a cluster which depends on what _namespace_ you pick. You can optionally ask for
_cycling_ containers in which case any container previously running in the cluster will be phased out.

The **kill** command will gracefully phase containers out (e.g they will be asked to stop whatever they are doing and
go into idling). Any underlying Marathon_ application whose containers are all dead will the be automatically
deleted.

The **scale** command will scale the number of pod instances in your cluster. This is equivalent to scaling instance
counts on Marathon_ but with Ochopod_ being instructed to prepare itself beforehand.

You can inspect your clusters at runtime using for instance the **grep**, **info** or **log** commands. The **poll** 
command will report user-defined metrics.

CI integration
**************

Some of the tools support a *-j* switch which will format their output to JSON. This can be used for instance to
integrate smoothly with a CI system such as Jenkins_ ! Please note the only thing you need to setup is the portal IP
address (e.g no tools to install locally).

The **ping** tool has been provided to allow direct interactions with the running containers. You can send arbitrary
YAML_ data (some commands or maybe some updated configuration settings) to whatever cluster(s). The Ochopod_ script
running on those containers has the option to implement custom logic to react to that YAML_ data and respond back. This
is a great way to quickly add controlling logic driven for instance from a Jenkins_ slave.

.. _Jenkins: https://jenkins-ci.org/
.. _Marathon: https://mesosphere.github.io/marathon/
.. _Mesos: http://mesos.apache.org/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Python: https://www.python.org/
.. _YAML: http://yaml.org/
