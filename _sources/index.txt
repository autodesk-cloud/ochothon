
Overview
========

Ochothon
_________

Ochothon is a little add-on you can drop onto a Mesos_ cluster running Marathon_ to quickly get started with Ochopod_.
It comes with a little web-shell and provides lean remoting as well. We embed a bunch of tools that allow you to list,
query, deploy and shutdown your Ochopod_ containers.

It is 100% made of Python_ with a dash of JQuery_ for the web-shell !

Cool examples
_____________

Our little CLI turns your dev/ops tasks into sheer pleasure ! No more headache with complicated APIs and undocumented
tools ! You don't even have anything to install !

Need to check if you have some Kafka_ brokers deployed on your Mesos_ cluster ?

.. code:: bash

    > grep *kafka*
    <*kafka*> -> 100% replies (1 pods total) ->

    cluster               |  pod IP          |  process  |  state
                          |                  |           |
    big.data.kafka #2     |  10.171.105.235  |  running  |  leader

Need to quickly stop Redis_, do stuff and restart it ?

.. code:: bash

    > off *redis
    <*redis> -> 100% replies, 1 pods off

    > on *redis
    <*redis> -> 100% replies, 1 pods on

Need to know on what port your containerized Zookeeper_ ensemble is listening on ?

.. code:: bash

    > port 2181 *zookeeper
    <*zookeeper> -> 100% replies (3 pods total) ->

    cluster                  |  node IP         |  TCP
                             |                  |
    my.project.zookeeper #1  |  54.81.20.224    |  9001
    my.project.zookeeper #2  |  54.198.16.240   |  1029
    my.project.zookeeper #3  |  54.157.129.239  |  1026
..

Want to push a new build for your API tier and gracefully phase out the old containers ?

.. code:: bash

    > deploy api.yml -c -n frontend
    100% success (spawned 4 pods)
..

Need to phase all your test clusters out in one go ?

.. code:: bash

    > kill test.*
    100% success (6 dead pods)

Contents
________

.. toctree::
   :maxdepth: 3

   concepts
   portal
   tools

Indices and tables
__________________

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _JQuery: https://jquery.com/
.. _Kafka: http://kafka.apache.org/
.. _Marathon: https://mesosphere.github.io/marathon/
.. _Mesos: http://mesos.apache.org/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Python: https://www.python.org/
.. _Redis: http://redis.io/
.. _Zookeeper: http://zookeeper.apache.org/

