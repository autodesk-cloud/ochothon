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
import json
import logging
import os

from ochopod.core.fsm import diagnostic
from ochopod.core.utils import merge, retry, shell
from random import choice
from requests import get, put, post
from threading import Thread
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


class _Automation(Thread):

    def __init__(self, proxy, cluster, strict, timeout, version):
        super(_Automation, self).__init__()

        self.cluster = cluster
        self.out = \
            {
                'ok': False,
                'up': []
            }
        self.proxy = proxy
        self.strict = strict
        self.timeout = timeout
        self.version = version

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

            #
            # - first peek and see what pods we have
            # - they should all map to one single marathon application (abort if not)
            # - we'll use the application identifier to retrieve the configuration json later on
            #
            def _query(zk):
                replies = fire(zk, self.cluster, 'info')
                return [hints['application'] for (_, hints, _) in replies.values()]

            js = run(self.proxy, _query)
            assert len(set(js)) == 1, '%s is mapping to 2+ marathon applications' % self.cluster
            app = js[0]

            #
            # - fetch the various versions for our app
            # - we want to get hold of the most recent configuration
            #
            url = 'http://%s/v2/apps/%s/versions' % (master, app)
            reply = get(url, headers=headers)
            code = reply.status_code
            logger.debug('-> %s (HTTP %d)' % (url, code))
            assert code == 200 or code == 201, 'delete failed (HTTP %d)' % code
            js = reply.json()

            #
            # - retrieve the latest one
            # - keep the docker container configuration and the # of tasks around
            #
            last = js['versions'][0]
            url = 'http://%s/v2/apps/%s/versions/%s' % (master, app, last)
            reply = get(url, headers=headers)
            code = reply.status_code
            logger.debug('-> %s (HTTP %d)' % (url, code))
            assert code == 200 or code == 201, 'delete failed (HTTP %d)' % code
            js = reply.json()

            spec = js['container']
            tag = spec['docker']['image']
            capacity = js['instances']

            #
            # - kill all the pods using a POST /control/kill
            # - wait for them to be dead
            #
            @retry(timeout=self.timeout, pause=0)
            def _spin():
                def _query(zk):
                    replies = fire(zk, self.cluster, 'control/kill', timeout=self.timeout)
                    return [(code, seq) for seq, _, code in replies.values()]

                #
                # - fire the request one or more pods
                # - wait for every pod to report back a HTTP 410 (GONE)
                # - this means the ochopod state-machine is now idling (e.g dead)
                #
                js = run(self.proxy, _query)
                gone = sum(1 for code, _ in js if code == 410)
                assert gone == len(js), 'at least one pod is still running'
                return

            _spin()

            #
            # - grab the docker image
            # - just add a :<version> suffix (or replace it) but don't change the image  proper
            # - update the image and PUT the new configuration back
            # - marathon will then kill & re-start all the tasks
            #
            tokens = tag.split(':')
            spec['docker']['image'] = \
                '%s:%s' % (tag, self.version) if len(tokens) < 2 else '%s:%s' % (tokens[0], self.version)
            js = \
                {
                    'container': spec
                }

            url = 'http://%s/v2/apps/%s' % (master, app)
            reply = put(url, data=json.dumps(js), headers=headers)
            code = reply.status_code
            logger.debug('-> %s (HTTP %d)' % (url, code))
            logger.debug(reply.text)
            assert code == 200 or code == 201, 'update failed (HTTP %d)' % code

            #
            # - the pods should now be starting
            # - wait for all the pods to be in the 'running' mode (they are 'dead' right now)
            # - the sequence counters allocated to our new pods are returned as well
            #
            target = ['running'] if self.strict else ['stopped', 'running']
            @retry(timeout=self.timeout, pause=3, default={})
            def _spin():
                def _query(zk):
                    replies = fire(zk, self.cluster, 'info')
                    return [(hints['process'], seq) for seq, hints, _ in replies.values() if hints['process'] in target]

                js = run(self.proxy, _query)
                assert len(js) == capacity, 'not all pods running yet'
                return js

            js = _spin()
            up = [seq for _, seq in js]
            assert len(up) == capacity, '1+ pods still not up (%d/%d)' % (len(up), capacity)
            self.out['up'] = up
            self.out['ok'] = True

            logger.debug('%s : %d pods updated to version "%s"' % (self.cluster, capacity, self.version))

        except AssertionError as failure:

            logger.debug('%s : failed to bump -> %s' % (self.cluster, failure))

        except Exception as failure:

            logger.debug('%s : failed to bump -> %s' % (self.cluster, diagnostic(failure)))

    def join(self, timeout=None):

        Thread.join(self)
        return self.out


def go():

    class _Tool(Template):

        help = \
            '''
                Blah.
            '''

        tag = 'bump'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='+', help='clusters (can be a glob pattern, e.g foo*)')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')
            parser.add_argument('-t', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')
            parser.add_argument('-v', action='store', dest='version', type=str, default='latest', help='docker image version')
            parser.add_argument('--strict', action='store_true', dest='strict', help='waits until all pods are running')

        def body(self, args, unknown, proxy):

            assert len(args.clusters), 'at least one cluster is required'

            #
            # - run the workflow proper (one thread per container definition)
            #
            threads = {cluster: _Automation(
                proxy,
                cluster,
                args.strict,
                args.timeout,
                args.version) for cluster in args.clusters}

            #
            # - wait for all our threads to join
            #
            n = len(threads)
            outcome = {key: thread.join() for key, thread in threads.items()}
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            up = sum(len(js['up']) for _, js in outcome.items())
            logger.info(json.dumps(outcome) if args.json else '%d%% success (%d pods)' % (pct, up))
            return 0 if pct == 100 else 1

    return _Tool()