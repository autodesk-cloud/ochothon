## Ochothon

[![Join the chat at https://gitter.im/autodesk-cloud/ochothon](https://badges.gitter.im/autodesk-cloud/ochothon.svg)](https://gitter.im/autodesk-cloud/ochothon?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

### Overview

This project is a small development PaaS leveraging [**Ochopod**](https://github.com/autodesk-cloud/ochopod)
and overlaying it on top of [**Marathon**](https://mesosphere.github.io/marathon/). It is the Marathon equivalent of
[**Ochonetes**](https://github.com/autodesk-cloud/ochonetes).

You can either use any vanilla Mesos/Marathon setup or be cool and adopt [**DCOS**](https://mesosphere.com/) which
provides an elaborate VPC setup plus dashboard !

This proxy hosts our little toolkit that allows you to create, query and manage your Ochopod containers. It also lets
you CURL your commands directly which is a great way to build your very own
[**CI/CD pipeline**](https://github.com/autodesk-cloud/ci-ochopod) !

### Getting started

#### Step 1 : install the CLI locally

Simply install our CLI interface which only requires [**Python 2.7+**](https://www.python.org/). You will then get
access to a multi-purpose **ocho** command-line script. For instance:

```
$ pip install git+https://github.com/autodesk-cloud/ochothon.git
$ ocho
usage: ocho [-h] command [extra arguments [extra arguments ...]]
ocho: error: too few arguments
```

#### Step 2 : install DCOS

You know how to do it. Just peruse their [**documentation**](http://beta-docs.mesosphere.com/install/awscluster/). The
script will gently deploy for you the whole stack inside of a VPC (plus you get access to their very cool dashboard).
Make sure to specify at least one public slave to run our proxy.

#### Step 3 : deploy the proxy container

We use a simple proxy mechanism to interact with our containers. Just use the attached
[**dcos.json**](https://github.com/autodesk-cloud/ochothon/blob/master/dcos.json) configuration to
set it up. If you wish to secure your proxy you can edit this file and define a secret token (which is used for
internal SHA1-HMAC challenges). For instance:

```
"ochothon_token": "my cool secret token"
```

Now issue a HTTP POST to one of your masters in order to spawn the proxy task:

```
$ curl -s -XPOST http://<MASTER IP>:8080/v2/apps -d@dcos.json -H "Content-Type: application/json"
```

This is pretty much it. Just wait for the _ocho-proxy_ task to be up and check from where it is running (you can do
this using the Marathon web UI for instance).

Note its internal EC2 IP address (usually something like _ip-172-20-0-11.ec2.internal_). Go in your AWS EC2 console
and find out what slave matches it. What you want of course it the slave public IP (e.g the one you can reach from your
workstation). That IP (or the corresponding hostname) will be the _only thing you need to access from now on_ (you can
for instance add it to your local _/etc/hosts_). You can easily firewall it as well depending on your needs.

If you happen to kill the task do not panic and just re-create a new one (it is completely stateless).

#### Step 4 : testing

Simply run the CLI and type ```help```. You should get a response back with the list of supported tools. For instance:

```
$ ocho cli my-cluster
welcome to the ocho CLI ! (CTRL-C to exit)
my-cluster > help
available commands -> bump, deploy, exec, grep, kill, log, ls, off, on, poll, port, reset, scale
```

Please note you must have _my-cluster_ mapped to your proxy IP in _/etc/hosts_ for the above to work.

### Not using Mesos-DNS

If you wish to run the proxy on a generic Mesos/Marathon setup and are not planning to install
[**Mesos-DNS**](https://mesosphere.github.io/mesos-dns/) you will have to specify the IP for all your masters
manually.

You can do so by adding a **$MARATHON_MASTER** environment variable in the
[**JSON configuration**](https://github.com/autodesk-cloud/ochothon/blob/master/dcos.json). Use a simple
comma separated connection string and make sure to use private IP addresses. For instance:

```
    "env":
    {
        "ochopod_cluster":  "portal",
        "ochopod_debug":    "true",
        "ochopod_token":    "",
        "MARATHON_MASTER":  "10.37.202.103:8080,10.169.225.66:8080"
    }
```

### The CLI

You are now all setup and can remotely issue commands to the proxy. Are you afraid of using CURL or feel lazy ? No
problemo, use our little self-contained CLI ! You just need to have [**Python 2.7+**](https://www.python.org/)
installed locally. You can set the **$OCHOPOD_PROXY** environment variable to avoid passing the proxy IP on the command
line. Any command typed in that interactive session will be relayed to your proxy ! If you prefer to CURL directory
you can do so as well.

If you are communicating with a proxy setup with a secret token you **must** export the **$OCHOPOD_TOKEN** environment
variable and set it to the right value. Not setting it or setting it to the wrong value will result in a failure.

The proxy supports a whole set of tools doing various things. Just type ```help``` in the CLI to get a list of what is
there. Each tool also has supports a --help switch that will print out all the details you need to know. As
an example:

```
$ ocho cli my-cluster
welcome to the ocho CLI ! (CTRL-C to exit)
my-cluster > help
available commands -> bump, deploy, exec, grep, kill, log, ls, off, on, poll, port, reset, scale

my-cluster > grep --help
usage: ocho grep [-h] [-d] [clusters [clusters ...]]

Displays high-level information for the specified cluster(s).

positional arguments:
  clusters     1+ clusters (can be a glob pattern, e.g foo*)

optional arguments:
  -h, --help   show this help message and exit
  -d, --debug  debug mode
```

### Template images

You can easily get started with your own image by running ```ocho init```. This utility will clone the specified
repository locally and prep it with everything you need. For instance:

```
$ ocho init
> enter a short identifier to describe what the image does (e.g web or database): my-app
> enter the docker repo/image to push to upon a CI build (e.g foo/bar): opaugam/ochopod-my-image
template ready in ochopod-marathon-my-app/
```

### Final check

You are all set. Use the _grep_ tool and you should see the portal itself. For instance:

```
$ ocho cli my-cluster
welcome to the ocho CLI ! (CTRL-C to exit)
my-cluster > grep
<*> -> 100% replies (1 pods total) ->

cluster              |  pod IP         |  process  |  state
                     |                 |           |
marathon.portal #1   |  10.169.225.66  |  running  |  leader
```

### Documentation

You can [**peruse our online documentation**](http://autodesk-cloud.github.io/ochothon/) for examples, design notes
and more !

The [**Sphinx**](http://sphinx-doc.org/) materials can be found under docs/. Just go in there and build for your
favorite target, for instance:

```
$ cd docs
$ make html
```

The docs will be written to _docs/_build/html_. This is all Sphinx based and you have many options and knobs to
tweak should you want to customize the output.

### More examples

Check out my [**git repositories**](https://github.com/opaugam) for images, code samples & more !

### Support

Contact autodesk.cloud.opensource@autodesk.com for more information about this project.

### License

© 2015 Autodesk Inc.
All rights reserved

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.