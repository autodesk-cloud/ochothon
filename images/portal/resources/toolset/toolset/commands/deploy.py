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

from ochopod.core.fsm import diagnostic, shutdown
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

    def __init__(self, proxy, template, overrides, namespace, pods, cycle):
        super(_Automation, self).__init__()

        self.cycle = cycle
        self.namespace = namespace
        self.out = \
            {
                'ok': False,
                'up': [],
                'down': []
            }
        self.overrides = overrides
        self.pods = pods
        self.proxy = proxy
        self.template = template

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
                # - add the ochopod control port if not specified
                #
                cfg = yaml.load(f)
                if 8080 not in cfg['ports']:
                    cfg['ports'].append(8080)

                #
                # - add the settings block if not already there
                #
                if not 'settings' in cfg:
                    cfg['settings'] = {}

                #
                # - timestamp the application (we really want a new uniquely identified application)
                # - lookup the optional overrides and merge with our pod settings if specified
                # - this is what happens when the -o option is used
                #
                suffix = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H-%M-%S')
                qualified = '%s.%s' % (self.namespace, cfg['cluster'])
                application = 'ochopod.%s-%s' % (qualified, suffix)
                if qualified in self.overrides:

                    blk = self.overrides[qualified]
                    logger.debug('%s : overriding %d settings (%s)' % (self.template, len(blk), qualified))
                    cfg['settings'] = merge(cfg['settings'], blk)

                def _nullcheck(cfg, prefix):

                    #
                    # - walk through the settings and flag any null value
                    #
                    missing = []
                    for key, value in cfg.items():
                        if value is None:
                            missing += ['%s.%s' % ('.'.join(prefix), key)]
                        elif isinstance(value, dict):
                            missing += _nullcheck(value, prefix + [key])

                    return missing

                missing = _nullcheck(cfg['settings'], ['pod'])
                assert not missing, '%d setting(s) missing ->\n\t - %s' % (len(missing), '\n\t - '.join(missing))

                #
                # - lookup our all the pods for that identifier
                # - get their sequence indices (we'll use it to phase out them out)
                # - if the target # of pods we want is not specified default to 1 unless we are cycling
                # - set it to the current # of pods in that case
                #
                def _query(zk):
                    replies = fire(zk, qualified, 'info')
                    return [seq for _, (seq, _, code) in replies.items() if code == 200]

                prev = run(self.proxy, _query)
                if self.cycle and not self.pods:
                    self.pods = len(prev)
                elif not self.pods:
                    self.pods = 1

                #
                # - setup our port list
                # - the marathon pods must by design map /etc/mesos
                #
                ports = [{'containerPort': port} for port in cfg['ports']]
                spec = \
                    {
                        'id': application,
                        'instances': self.pods,
                        'env':
                            {
                                'ochopod_cluster': cfg['cluster'],
                                'ochopod_namespace': self.namespace,
                                'ochopod_application': qualified,
                                'pod': json.dumps(cfg['settings'])
                            },
                        'container':
                            {
                                'type': 'DOCKER',
                                'docker':
                                    {
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
                @retry(timeout=60, pause=1, default={})
                def _spin():
                    def _query(zk):
                        replies = fire(zk, qualified, 'info')
                        return [(hints['process'], seq) for seq, hints, _ in replies.values()
                                if hints['application'] == application]

                    js = run(self.proxy, _query)
                    assert len(js) == self.pods, 'not all pods running yet'
                    return js

                js = _spin()
                running = sum(1 for state, _ in js if state is not 'dead')
                up = [seq for _, seq in js]
                self.out['up'] = up
                self.out['ok'] = self.pods == running
                logger.debug('%s : %d/%d pods are running -> %s' % (self.template, running, self.pods, ', '.join(['#%d' % seq for seq in up])))

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

                elif self.cycle:

                    #
                    # - phase out & clean-up the pods that were previously running
                    # - simply exec() the kill tool for this
                    #
                    logger.debug('%s : phasing out %s' % (self.template, ', '.join(['# %d' % seq for seq in prev])))
                    code, lines = shell('toolset kill %s -i %s -d' % (qualified, ' '.join(['%d' % seq for seq in prev])))
                    assert code == 0, 'failed to run <kill>'
                    self.out['down'] = prev

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
                Spawns a marathon application for each of the specified cluster(s). The tool will wait for all containers
                to be running (but not necessarily configured & clustered). If no container ended up being deployed the
                underlying marathon application will automatically get deleted. If -c is specified any pod previously
                running for the specified cluster(s) will be gracefully phased out once the new pods are up.
            '''

        tag = 'deploy'

        def customize(self, parser):

            parser.add_argument('containers', type=str, nargs='*', default='*', help='1+ container yaml definitions (can be a glob pattern, e.g foo*)')
            parser.add_argument('-c', action='store_true', dest='cycle', help='cycling (e.g the current pods will be phased out')
            parser.add_argument('-n', action='store', dest='namespace', type=str, default='default', help='cluster namespace')
            parser.add_argument('-o', action='store', dest='overrides', type=str, help='overrides yaml file')
            parser.add_argument('-p', action='store', dest='pods', type=int, help='number of pods to deploy')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')

        def body(self, args, proxy):

            assert len(args.containers), 'at least one container definition is required'

            #
            # - load the overrides from yaml if specified
            #
            overrides = {}
            if args.overrides:
                try:
                    with open(args.overrides, 'r') as f:
                        overrides = yaml.load(f)

                except IOError:

                    logger.debug('unable to load %s, skipping overrides' % args.overrides)

                except YAMLError as failure:

                    if hasattr(failure, 'problem_mark'):
                        mark = failure.problem_mark
                        assert 0, '%s is invalid (line %s, column %s)' % (args.overrides, mark.line+1, mark.column+1)

            #
            # - run the workflow proper (one thread per container definition)
            #
            threads = {template: _Automation(proxy, template, overrides, args.namespace, args.pods, args.cycle) for template in args.containers}

            #
            # - wait for all our threads to join
            #
            n = len(threads)
            outcome = {key: thread.join() for key, thread in threads.items()}
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            up = sum(len(js['up']) for _, js in outcome.items())
            logger.info(json.dumps(outcome) if args.json else '%d%% success (spawned %d pods)' % (pct, up))
            return 0 if pct == 100 else 1

    return _Tool()