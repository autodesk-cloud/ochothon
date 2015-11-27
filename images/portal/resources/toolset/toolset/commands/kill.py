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
from ochopod.core.utils import retry
from random import choice
from requests import get, delete, post
from threading import Thread
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


class _Automation(Thread):

    def __init__(self, proxy, cluster, indices, timeout):
        super(_Automation, self).__init__()

        self.cluster = cluster
        self.out = \
            {
                'ok': False,
                'down': []
            }
        self.proxy = proxy
        self.indices = indices
        self.timeout = max(timeout, 5)

        self.start()

    def run(self):
        try:

            #
            # - we need to pass the framework master IPs around (ugly)
            #
            assert 'MASTERS' in os.environ, '$MASTERS not specified (check your portal pod)'
            master = choice(os.environ['MASTERS'].split(','))
            headers = \
                {
                    'content-type': 'application/json',
                    'accept': 'application/json'
                }

            #
            # - kill all (or part of) the pods using a POST /control/kill
            # - wait for them to be dead
            # - warning, /control/kill will block (hence the 5 seconds timeout)
            #
            @retry(timeout=self.timeout, pause=0)
            def _spin():
                def _query(zk):
                    replies = fire(zk, self.cluster, 'control/kill', subset=self.indices, timeout=self.timeout)
                    return [(code, seq) for seq, _, code in replies.values()]

                #
                # - fire the request one or more pods
                # - wait for every pod to report back a HTTP 410 (GONE)
                # - this means the ochopod state-machine is now idling (e.g dead)
                #
                js = run(self.proxy, _query)
                gone = sum(1 for code, _ in js if code == 410)
                assert gone == len(js), 'at least one pod is still running'
                return [seq for _, seq in js]

            down = _spin()
            self.out['down'] = down
            assert down, 'the cluster is either invalid or empty'
            logger.debug('%s : %d dead pods -> %s' % (self.cluster, len(down), ', '.join(['#%d' % seq for seq in down])))

            #
            # - now peek and see what pods we have
            # - we want to know what the underlying marathon application & task are
            #
            def _query(zk):
                replies = fire(zk, self.cluster, 'info', subset=self.indices)
                return [(hints['application'], hints['task']) for _, hints, _ in replies.values()]

            js = run(self.proxy, _query)
            rollup = {key: [] for key in set([key for key, _ in js])}
            for app, task in js:
                rollup[app] += [task]

            #
            # - go through each application
            # - query the it and check how many tasks it currently has
            # - the goal is to check if we should nuke the whole application or not
            #
            for app, tasks in rollup.items():

                url = 'http://%s/v2/apps/%s/tasks' % (master, app)
                reply = get(url, headers=headers)
                code = reply.status_code
                logger.debug('%s : -> %s (HTTP %d)' % (self.cluster, url, code))
                assert code == 200, 'task lookup failed (HTTP %d)' % code
                js = reply.json()

                if len(tasks) == len(js['tasks']):

                    #
                    # - all the containers running for that application were reported as dead
                    # - issue a DELETE /v2/apps to nuke the whole thing
                    #
                    url = 'http://%s/v2/apps/%s' % (master, app)
                    reply = delete(url, headers=headers)
                    code = reply.status_code
                    logger.debug('%s : -> %s (HTTP %d)' % (self.cluster, url, code))
                    assert code == 200 or code == 204, 'application deletion failed (HTTP %d)' % code

                else:

                    #
                    # - we killed a subset of that application's pods
                    # - cherry pick the underlying tasks and delete them at once using POST v2/tasks/delete
                    #
                    js = \
                        {
                            'ids': tasks
                        }

                    url = 'http://%s/v2/tasks/delete?scale=true' % master
                    reply = post(url, data=json.dumps(js), headers=headers)
                    code = reply.status_code
                    logger.debug('-> %s (HTTP %d)' % (url, code))
                    assert code == 200 or code == 201, 'delete failed (HTTP %d)' % code

            self.out['ok'] = True

        except AssertionError as failure:

            logger.debug('%s : failed to kill -> %s' % (self.cluster, failure))

        except Exception as failure:

            logger.debug('%s : failed to kill -> %s' % (self.cluster, diagnostic(failure)))

    def join(self, timeout=None):

        Thread.join(self)
        return self.out


def go():

    class _Tool(Template):

        help = \
            '''
                Gracefully shuts the ochopod containers down for the specified cluster(s). Individual containers can
                also be cherry-picked by specifying their sequence index and using -i. Any marathon application whose
                containers are *all* dead will automatically get deleted. Please note you must by default use -i and
                specify what containers to kill. If you want to kill multiple containers at once you must specify
                --force.

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'kill'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='+', help='cluster(s) (can be a glob pattern, e.g foo*)')
            parser.add_argument('-i', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')
            parser.add_argument('-t', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, _, proxy):

            assert args.force or args.indices, 'you must specify --force if -i is not set'

            #
            # - run the workflow proper (one thread per cluster identifier)
            #
            threads = {cluster: _Automation(
                proxy,
                cluster,
                args.indices,
                args.timeout) for cluster in args.clusters}

            #
            # - wait for all our threads to join
            #
            n = len(threads)
            outcome = {key: thread.join() for key, thread in threads.items()}
            dead = sum(len(js['down']) for _, js in outcome.items())
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            logger.info(json.dumps(outcome) if args.json else '%d%% success (-%d pods)' % (pct, dead))
            return 0 if pct == 100 else 1

    return _Tool()