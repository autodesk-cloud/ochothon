Concepts
========

Architecture
____________

Overview
********

Ochothon is simply a Marathon_ application that runs a little *portal* Python_ application (which interestingly is
an Ochopod_ container itself). The *portal*'s job is to host a set of tools that will talk to the Marathon_ masters
and Ochopod_ containers (for instance to deploy stuff).

Why using such a proxy mechanism ? Well, mostly to encapsulate logic and avoid ending up with a fat CLI on your end.
Additionally this allows to have all the inter-container I/O performed within the cluster (e.g no firewalling headache
for you). Of course for a real PaaS this is also where you would inject access control, credentials and so on.

In other words you deploy our *proxy* application and talk to it from then on. Easy.

Why Ochopod ?
*************

Because Mesos_ - even if totally awesome - will not perform fine grained orchestration for you. You know what I
mean by fine grained: the ability to form relationships between your containers without the need for an extrinsic
control mechanism (look at the Ochopod_ documentation for more details).

In our case we will leverage the *application* semantics from Marathon_. One Ochopod_ cluster maps to one
or more applications. Each application runs a bunch of Mesos_ *tasks* which in turn run a Docker_ container embedding
Ochopod_.

Mesos_ will remap ports and this needs to be taken into account when containers need to reach each other. Ochopod_ will
manage this for you.

Where is Zookeeper ?
********************

As you remember Ochopod_ relies on Zookeeper_ for its internal leader elections and metadata storage. Our containers
will simply all mount */ect/mesos/* (e.g where the underlying slave stores its Mesos_ configuration) and use what's
inside to find out where Zookeeper_ is. So in other words we piggy back on the ensemble used by Mesos_.

.. _Docker: https://www.docker.com/
.. _Marathon: https://mesosphere.github.io/marathon/
.. _Mesos: http://mesos.apache.org/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Python: https://www.python.org/
.. _Zookeeper: http://zookeeper.apache.org/

