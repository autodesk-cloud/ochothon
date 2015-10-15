#! /usr/bin/env python
#
# Copyright (c) 2015 Autodesk Inc.
# All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Minimalistic self-contained wrapper performing the curl calls to the ochopod proxy. The input is
turned into a POST -H X-Shell:<> to the proxy at port TCP 9000. Any token from that input that
matches a local file (wherever the script is running from) will force an upload for the said file.
This mechanism is used for instance to upload the container definition YAML files when deploying a
new cluster.

The proxy ip or hostname is either passed as the first command-line argument or vi a $OCHOPOD_PROXY.
Type "help" to get the list of supported commands.

For instance:

 $ ocho cli my-cluster
 welcome to the ocho CLI ! (CTRL-C or exit to get out)
 my-cluster > help
 available commands -> bump, deploy, grep, kill, log, ls, nodes, off, on, ping, poll, port

You can also run a one-shot command. For instance if you just need to list all your pods:

 $ ocho cli my-cluster ls
 3 pods, 100% replies ->

 cluster                                        |  ok   |  status
                                                |       |
 marathon.portal                                |  1/1  |
 test.web-server                                |  2/2  |
"""

import cmd
import json
import os

from common import shell
from os.path import basename, expanduser, isfile
from sys import exit


def cli(args):

    class Shell(cmd.Cmd):

        def __init__(self, ip):
            cmd.Cmd.__init__(self)
            self.prompt = '%s > ' % ip
            self.ruler = '-'

        def precmd(self, line):
            return 'shell %s' % line if line not in ['exit'] else line

        def emptyline(self):
            pass

        def do_exit(self, _):
            raise KeyboardInterrupt

        def do_shell(self, line):
            if line:
                tokens = line.split(' ')

                #
                # - update from steven -> reformat the input line to handle indirect paths transparently
                # - for instance ../foo.bar will become foo.bar with the actual file included in the multi-part post
                #
                files = ['-F %s=@%s' % (basename(token), expanduser(token)) for token in tokens if isfile(expanduser(token))]
                line = ' '.join([basename(token) if isfile(expanduser(token)) else token for token in tokens])
                snippet = 'curl -X POST -H "X-Shell:%s" %s %s:9000/shell' % (line, ' '.join(files), ip)
                code, out = shell(snippet)
                js = json.loads(out.decode('utf-8'))
                print(js['out'] if code is 0 else 'i/o failure (is the proxy down ?)')

    try:

        #
        # - partition ip and args by looking for OCHOPOD_PROXY first
        # - if OCHOPOD_PROXY is not used, treat the first argument as the ip
        #
        if 'OCHOPOD_PROXY' in os.environ:
            ip = os.environ['OCHOPOD_PROXY']
        elif len(args):
            ip = args[0]
            args = args[1:] if len(args) > 1 else []
        else:
            print('either set $OCHOPOD_PROXY or pass the proxy IP as an argument')
            exit(1)

        #
        # - determine whether to run in interactive or non-interactive mode
        #
        if len(args):
            command = " ".join(args)
            Shell(ip).do_shell(command)
        else:
            print('welcome to the ocho CLI ! (CTRL-C or exit to get out)')
            Shell(ip).cmdloop()

    except KeyboardInterrupt:
        exit(0)

    except Exception as failure:
        print('internal failure <- %s' % str(failure))
        exit(1)