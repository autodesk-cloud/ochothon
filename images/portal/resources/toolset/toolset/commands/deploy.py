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
import datetime
import json
import logging
import os
import time
import yaml

from ochopod.core.fsm import diagnostic
from ochopod.core.utils import merge, retry, shell
from random import choice
from requests import delete, post
from threading import Thread
from toolset.io import fire, run
from toolset.tool import Template
from yaml import YAMLError

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


class _Automation(Thread):

    def __init__(self, proxy, template, overrides, namespace, pods, suffix, timeout, strict):
        super(_Automation, self).__init__()

        self.namespace = namespace
        self.out = \
            {
                'ok': False,
                'up': []
            }
        self.overrides = overrides
        self.pods = pods
        self.proxy = proxy
        self.template = template
        self.suffix = suffix
        self.strict = strict
        self.timeout = max(timeout, 5)

        self.start()

    def run(self):
        try:

            #
            # - we need to pass the framework master IPs around (ugly)
            #
            assert 'MARATHON_MASTER' in os.environ, '$MARATHON_MASTER not specified (check your portal pod)'
            master = choice(os.environ['MARATHON_MASTER'].split(','))
            headers = \
                {
                    'content-type': 'application/json',
                    'accept': 'application/json'
                }

            with open(self.template, 'r') as f:

                #
                # - parse the template yaml file (e.g container definition)
                #
                raw = yaml.load(f)
                assert raw, 'empty YAML input (user error ?)'

                #
                # - merge with our defaults
                # - we want at least the cluster & image settings
                # - TCP 8080 is added by default to the port list
                #
                defaults = \
                    {
                        'start': True,
                        'debug': False,
                        'settings': {},
                        'ports': [8080],
                        'verbatim': {}
                    }

                cfg = merge(defaults, raw)
                assert 'cluster' in cfg, 'cluster identifier undefined (user error ?)'
                assert 'image' in cfg, 'docker image undefined (user error ?)'

                #
                # - if a suffix is specified append it to the cluster identifier
                #
                if self.suffix:
                    cfg['cluster'] = '%s-%s' % (cfg['cluster'], self.suffix)

                #
                # - timestamp the application (we really want a new uniquely identified application)
                # - lookup the optional overrides and merge with our pod settings if specified
                # - this is what happens when the -o option is used
                #
                stamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H-%M-%S')
                qualified = '%s.%s' % (self.namespace, cfg['cluster'])
                application = 'ochopod.%s-%s' % (qualified, stamp)
                if qualified in self.overrides:

                    blk = self.overrides[qualified]
                    logger.debug('%s : overriding %d settings (%s)' % (self.template, len(blk), qualified))
                    cfg['settings'] = merge(cfg['settings'], blk)

                def _nullcheck(cfg, prefix):

                    #
                    # - walk through the settings and flag any null value
                    #
                    missing = []
                    if cfg is not None:
                        for key, value in cfg.items():
                            if value is None:
                                missing += ['%s.%s' % ('.'.join(prefix), key)]
                            elif isinstance(value, dict):
                                missing += _nullcheck(value, prefix + [key])

                    return missing

                missing = _nullcheck(cfg['settings'], ['pod'])
                assert not missing, '%d setting(s) missing ->\n\t - %s' % (len(missing), '\n\t - '.join(missing))

                #
                # - if we still have no target default it to 1 single pod
                #
                if not self.pods:
                    self.pods = 1

                #
                # - setup our port list
                # - the port binding is specified either by an integer (container port -> dynamic mesos port), by
                #   two integers (container port -> host port) or by an integer followed by a * (container port ->
                #   same port on the host)
                # - the marathon pods must by design map /etc/mesos
                #
                def _parse_port(token):
                    if isinstance(token, int):
                        return {'containerPort': token}
                    elif isinstance(token, str) and token.endswith(' *'):
                        port = int(token[:-2])
                        return {'containerPort': port, 'hostPort': port}
                    elif isinstance(token, str):
                        ports = token.split(' ')
                        assert len(ports) == 2, 'invalid port syntax (must be two integers separated by 1+ spaces)'
                        return {'containerPort': int(ports[0]), 'hostPort': int(ports[1])}
                    else:
                        assert 0, 'invalid port syntax ("%s")' % token

                #
                # - note the marathon-ec2 ochopod bindings will set the application hint automatically
                #   via environment variable (e.g no need to specify it here)
                # - make sure to mount /etc/mesos and /opt/mesosphere to account for various mesos installs
                #
                ports = [_parse_port(token) for token in cfg['ports']] if 'ports' in cfg else []
                spec = \
                    {
                        'id': application,
                        'instances': self.pods,
                        'env':
                            {
                                'ochopod_cluster': cfg['cluster'],
                                'ochopod_debug': str(cfg['debug']).lower(),
                                'ochopod_start': str(cfg['start']).lower(),
                                'ochopod_namespace': self.namespace,
                                'pod': json.dumps(cfg['settings'])
                            },
                        'container':
                            {
                                'type': 'DOCKER',
                                'docker':
                                    {
                                        'forcePullImage': True,
                                        'image': cfg['image'],
                                        'network': 'BRIDGE',
                                        'portMappings': ports
                                    },
                                'volumes':
                                    [
                                        {
                                            'containerPath': '/etc/mesos',
                                            'hostPath': '/etc/mesos',
                                            'mode': 'RO'
                                        },
                                        {
                                            'containerPath': '/opt/mesosphere',
                                            'hostPath': '/opt/mesosphere',
                                            'mode': 'RO'
                                        }
                                    ]
                            }
                    }

                #
                # - if we have a 'verbatim' block in our image definition yaml, merge it now
                #
                if 'verbatim' in cfg:
                    spec = merge(cfg['verbatim'], spec)

                #
                # - pick a marathon master at random
                # - fire the POST /v2/apps to create our application
                # - this will indirectly spawn our pods
                #
                url = 'http://%s/v2/apps' % master
                reply = post(url, data=json.dumps(spec), headers=headers)
                code = reply.status_code
                logger.debug('-> %s (HTTP %d)' % (url, code))
                assert code == 200 or code == 201, 'submission failed (HTTP %d)' % code

                #
                # - wait for all the pods to be in the 'running' mode
                # - the 'application' hint is set by design to the marathon application identifier
                # - the sequence counters allocated to our new pods are returned as well
                #
                target = ['dead', 'running'] if self.strict else ['dead', 'stopped', 'running']
                @retry(timeout=self.timeout, pause=3, default={})
                def _spin():
                    def _query(zk):
                        replies = fire(zk, qualified, 'info')
                        return [(hints['process'], seq) for seq, hints, _ in replies.values()
                                if hints['application'] == application and hints['process'] in target]

                    js = run(self.proxy, _query)
                    assert len(js) == self.pods, 'not all pods running yet'
                    return js

                js = _spin()
                running = sum(1 for state, _ in js if state is not 'dead')
                up = [seq for _, seq in js]
                self.out['up'] = up
                self.out['ok'] = self.pods == running
                logger.debug('%s : %d/%d pods are running ' % (self.template, running, self.pods))

                if not up:

                    #
                    # - nothing is running (typically because the image has an issue and is not
                    #   not booting the ochopod script for instance, which happens often)
                    # - in that case fire a HTTP DELETE against the marathon application to clean it up
                    #
                    url = 'http://%s/v2/apps/%s' % (master, application)
                    reply = delete(url, headers=headers)
                    code = reply.status_code
                    logger.debug('-> %s (HTTP %d)' % (url, code))
                    assert code == 200 or code == 204, 'application deletion failed (HTTP %d)' % code

        except AssertionError as failure:

            logger.debug('%s : failed to deploy -> %s' % (self.template, failure))

        except YAMLError as failure:

            if hasattr(failure, 'problem_mark'):
                mark = failure.problem_mark
                logger.debug('%s : invalid deploy.yml (line %s, column %s)' % (self.template, mark.line+1, mark.column+1))

        except Exception as failure:

            logger.debug('%s : failed to deploy -> %s' % (self.template, diagnostic(failure)))

    def join(self, timeout=None):

        Thread.join(self)
        return self.out


def go():

    class _Tool(Template):

        help = \
            '''
                Spawns a marathon application for each of the specified cluster(s). The tool will by default wait for
                all containers to be up (but not necessarily configured & clustered yet) while using the --strict
                switch will ensure we wait for all containers to be fully configured.

                If no container ended up being deployed the underlying marathon application will automatically get
                deleted.It is possible to add a suffix to the cluster identifier defined in the yaml configuration
                by using the -s option (typically to run the same functionality in different contexts).

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.

                Please note we force a docker image pull when instantiating the new application.
            '''

        tag = 'deploy'

        def customize(self, parser):

            parser.add_argument('containers', type=str, nargs='+', help='1+ YAML definitions (e.g marathon.yml)')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')
            parser.add_argument('-n', action='store', dest='namespace', type=str, default='marathon', help='namespace')
            parser.add_argument('-o', action='store', dest='overrides', type=str, nargs='+', help='overrides YAML file(s)')
            parser.add_argument('-p', action='store', dest='pods', type=int, help='number of pods to deploy')
            parser.add_argument('-s', action='store', dest='suffix', type=str, help='optional cluster suffix')
            parser.add_argument('-t', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')
            parser.add_argument('--strict', action='store_true', dest='strict', help='waits until all pods are running')

        def body(self, args, proxy):

            assert len(args.containers), 'at least one container definition is required'

            #
            # - load the overrides from yaml if specified
            #
            overrides = {}
            if not args.overrides:
                args.overrides = []

            for path in args.overrides:
                try:
                    with open(path, 'r') as f:
                        overrides.update(yaml.load(f))

                except IOError:

                    logger.debug('unable to load %s' % args.overrides)

                except YAMLError as failure:

                    if hasattr(failure, 'problem_mark'):
                        mark = failure.problem_mark
                        assert 0, '%s is invalid (line %s, column %s)' % (args.overrides, mark.line+1, mark.column+1)

            #
            # - run the workflow proper (one thread per container definition)
            #
            threads = {template: _Automation(
                proxy,
                template,
                overrides,
                args.namespace,
                args.pods,
                args.suffix,
                args.timeout,
                args.strict) for template in args.containers}

            #
            # - wait for all our threads to join
            #
            n = len(threads)
            outcome = {key: thread.join() for key, thread in threads.items()}
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            up = sum(len(js['up']) for _, js in outcome.items())
            logger.info(json.dumps(outcome) if args.json else '%d%% success (+%d pods)' % (pct, up))
            return 0 if pct == 100 else 1

    return _Tool()