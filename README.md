## Ochothon

### Overview

This project is a small development PaaS leveraging [**Ochopod**](https://github.com/autodesk-cloud/ochopod)
and overlaying it on top of [**Marathon**](https://mesosphere.github.io/marathon/). It is the Marathon equivalent of
[**Ochonetes**](https://github.com/autodesk-cloud/ochonetes).

Your containers will run by default in a VPC while you interact from your workstation with a proxy which provides a
self-contained web-shell ([**JQuery**](https://jquery.com/) rocks !). This proxy hosts our little toolkit that will
allow you to create, query and manage your ochopod containers. It also lets you CURL your commands directly which is
a great way to build your CI/CD pipeline !

Please note we **only support bindings to run over AWS** at this point.

### Getting started

#### Step 1 : install [**DCOS**](https://mesosphere.com/)

You know how to do it. Just peruse their [**documentation**](http://beta-docs.mesosphere.com/install/awscluster/). The
script will gently deploy for you the whole stack inside of a VPC (plus you get access to their very cool dashboard).
Make sure to specify at least one public slave to run our proxy.

Once the stack is up look where your Marathon masters are running from and note their private IPs.

#### Step 2 : deploy our proxy

We use a simple proxy mechanism to interact with our containers. Edit the provided ```dcos.json``` configuration and
specify the **internal** IP for each master (just the IP, not a URL) including port 8080. For instance:

```
"MARATHON_MASTER": "10.37.202.103:8080,10.169.225.66:8080"
```

_Please note this (clunky) procedure is temporary until a way to find out what the masters are from within a container
is implemented in Marathon._

Then launch that application using CURL. It will automatically be assigned to one of your public slaves. You can post
to the admin ELB that was deployed or directly to one of the masters (using its public IP of course). For instance:

```
$ curl -s -XPOST http://54.159.110.218:8080/v2/apps -d@dcos.json -H "Content-Type: application/json"
```

Wait a bit until the _ocho-proxy_ application is up and look at its only task. You can do this using the Marathon
web UI. Note its internal EC2 IP address (usually something like ```ip-172-20-0-11.ec2.internal```). Go in your AWS
EC2 console and find out what slave matches it. What you want of course it the slave public IP (e.g the one you can
reach from your workstation).

This IP (or the corresponding hostname, whatever you prefer) will be the _only thing you need to access from now on_.
You can easily firewall it depending on your needs. Simply use your browser and look the proxy node IP up on port 9000.
You should see our little web-shell (notice the elegant ascii art).

If you happen to kill the portal application do not panic and just re-create a new one (it is completely stateless).

### The CLI

You are now all setup and can remotely issue commands to the proxy. Are you afraid of using CURL or feel lazy ? No
problemo, use our little self-contained CLI ! You just need to have [**Python 2.7+**](https://www.python.org/)
installed locally:

```
$ chmod +x cli.py
$ ./cli.py <PROXY IP>
welcome to the ocho CLI ! (CTRL-C to exit)
>
```

You can set the $OCHOPOD_PROXY environment variable to avoid passing the proxy IP on the command line. Any command
typed in that interactive session will be relayed to your proxy ! If you prefer to CURL directory you can do so as
well.

The proxy supports a whole set of tools doing various things. Just type ```help``` in the CLI to get a list of what is
there. Each tool also has supports a ```---help``` switch that will print out all the details you need to know. As
an example:

```
$ ./cli.py
welcome to the ocho CLI ! (CTRL-C to exit)
> help
available commands -> deploy, grep, info, kill, log, ls, off, on

> grep --help
usage: ocho grep [-h] [-d] [clusters [clusters ...]]

Displays high-level information for the specified cluster(s).

positional arguments:
  clusters     1+ clusters (can be a glob pattern, e.g foo*)

optional arguments:
  -h, --help   show this help message and exit
  -d, --debug  debug mode
```

### Final check

You are all set. Use the _grep_ tool and you should see the portal itself. For instance:

```
$ ./cli.py
welcome to the ocho CLI ! (CTRL-C to exit)
> grep
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