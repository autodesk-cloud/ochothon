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
from requests import post, put
from threading import Thread
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


class _Automation(Thread):

    def __init__(self, proxy, cluster, factor, fifo, group, timeout):
        super(_Automation, self).__init__()

        self.cluster = cluster
        self.factor = factor
        self.fifo = fifo
        self.group = group
        self.out = \
            {
                'ok': False
            }
        self.proxy = proxy
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
            # - first peek and see what pods we have
            #
            def _query(zk):
                replies = fire(zk, self.cluster, 'info')
                return [(seq, hints['application'], hints['task']) for (seq, hints, _) in replies.values()]

            #
            # - remap a bit differently and get an ordered list of task identifiers
            # - we'll use that to kill the newest pods
            #
            js = run(self.proxy, _query)
            total = len(js)
            if self.group is not None:

                #
                # - if -g was specify apply the scaling to the underlying marathon application containing that pod
                # - be careful to update the task list and total # of pods
                #
                keys = {seq: key for (seq, key, _) in js}
                assert self.group in keys, '#%d is not a valid pod index' % self.group
                app = keys[self.group]
                tasks = [(seq, task) for (seq, key, task) in sorted(js, key=(lambda _: _[0])) if key == app]
                total = sum(1 for (_, key, _) in js if key == app)

            else:

                #
                # - check and make sure all our pods map to one single marathon application
                #
                keys = set([key for (_, key, _) in js])
                assert len(keys) == 1, '%s maps to more than one application, you must specify -g' % self.cluster
                tasks = [(seq, task) for (seq, _, task) in sorted(js, key=(lambda _: _[0]))]
                app = keys.pop()

            #
            # - infer the target # of pods based on the user-defined factor
            #
            operator = self.factor[0]
            assert operator in ['@', 'x'], 'invalid operator'
            n = float(self.factor[1:])
            target = n if operator == '@' else total * n

            #
            # - clip the target # of pods down to 1
            #
            target = max(1, int(target))
            self.out['delta'] = target - total
            if target > total:

                #
                # - scale the application capacity up
                #
                js = \
                    {
                        'instances': target
                    }

                url = 'http://%s/v2/apps/%s' % (master, app)
                reply = put(url, data=json.dumps(js), headers=headers)
                code = reply.status_code
                logger.debug('-> %s (HTTP %d)' % (url, code))
                assert code == 200 or code == 201, 'update failed (HTTP %d)' % code

                #
                # - wait for all our new pods to be there
                #
                @retry(timeout=self.timeout, pause=3, default={})
                def _spin():
                    def _query(zk):
                        replies = fire(zk, self.cluster, 'info')
                        return [seq for seq, _, _ in replies.values()]

                    js = run(self.proxy, _query)
                    assert len(js) == target, 'not all pods running yet'
                    return js

                _spin()

            elif target < total:

                #
                # - if the fifo switch is on make sure to pick the oldest pods for deletion
                #
                tasks = tasks[:total - target] if self.fifo else tasks[target:]

                #
                # - kill all (or part of) the pods using a POST /control/kill
                # - wait for them to be dead
                #
                @retry(timeout=self.timeout, pause=0)
                def _spin():
                    def _query(zk):
                        indices = [seq for (seq, _) in tasks]
                        replies = fire(zk, self.cluster, 'control/kill', subset=indices, timeout=self.timeout)
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
                # - delete all the underlying tasks at once using POST v2/tasks/delete
                #
                js = \
                    {
                        'ids': [task for (_, task) in tasks]
                    }

                url = 'http://%s/v2/tasks/delete?scale=true' % master
                reply = post(url, data=json.dumps(js), headers=headers)
                code = reply.status_code
                logger.debug('-> %s (HTTP %d)' % (url, code))
                assert code == 200 or code == 201, 'delete failed (HTTP %d)' % code

            self.out['ok'] = True

        except AssertionError as failure:

            logger.debug('%s : failed to scale -> %s' % (self.cluster, failure))

        except Exception as failure:

            logger.debug('%s : failed to scale -> %s' % (self.cluster, diagnostic(failure)))

    def join(self, timeout=None):

        Thread.join(self)
        return self.out


def go():

    class _Tool(Template):

        help = \
            '''
                Scales the specified clusters up or down. Scaling can be done using a target number of pods (-f @5 for
                instance), or by using a multiplier (e.g -f x0.75). By default the scaled clusters must map each to
                one single marathon application otherwise -g must be specified to differentiate them (in this case -g
                specifies a pod index we'll use to pick the right application).

                When scaling down (and phasing pods out) the --fifo can be used to kill the oldest pods first. The
                default is to kill the most recent pods (LIFO).

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'scale'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='+', help='clusters (can be a glob pattern, e.g foo*)')
            parser.add_argument('-f', action='store', dest='factor', default='+1', help='scaling factor, e.g x1.75')
            parser.add_argument('-g', action='store', type=int, dest='group', help='pod index')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')
            parser.add_argument('-t', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')
            parser.add_argument('--fifo', action='store_true', dest='fifo', help='fifo mode (scale down only)')

        def body(self, args, unknown, proxy):

            #
            # - run the workflow proper (one thread per cluster)
            #
            threads = {cluster: _Automation(
                proxy,
                cluster,
                args.factor,
                args.fifo,
                args.group,
                args.timeout) for cluster in args.clusters}

            #
            # - wait for all our threads to join
            #
            n = len(threads)
            outcome = {key: thread.join() for key, thread in threads.items()}
            delta = sum(js['delta'] for _, js in outcome.items())
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            logger.info(json.dumps(outcome) if args.json else '%d%% success (%+d pods)' % (pct, delta))
            return 0 if pct == 100 else 1

    return _Tool()