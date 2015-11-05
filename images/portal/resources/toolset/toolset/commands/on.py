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
                'on': []
            }
        self.proxy = proxy
        self.indices = indices
        self.timeout = max(timeout, 5)

        self.start()

    def run(self):
        try:

            def _query(zk):
                replies = fire(zk, self.cluster, 'control/on', subset=self.indices, timeout=self.timeout)
                return len(replies), [seq for seq, (_, _, code) in replies.items() if code == 200]

            total, js = run(self.proxy, _query)
            assert len(js) == total, '1 or more pod failed to stop'

            self.out['on'] = js
            self.out['ok'] = True

        except AssertionError as failure:

            logger.debug('%s : failed to switch on -> %s' % (self.cluster, failure))

        except Exception as failure:

            logger.debug('%s : failed to switch on -> %s' % (self.cluster, diagnostic(failure)))

    def join(self, timeout=None):

        Thread.join(self)
        return self.out

def go():

    class _Tool(Template):

        help = \
            '''
                Switches one or more containers on. Individual containers can also be cherry-picked by specifying
                their sequence index and using -i. Please note you must by default use -i and specify what containers
                to turn on. If you want to turn multiple containers on at once you must specify --force.

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'on'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='+', help='cluster(s) (can be a glob pattern, e.g foo*)')
            parser.add_argument('-i', '--indices', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')
            parser.add_argument('-t', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, unknown, proxy):

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
            dead = sum(len(js['on']) for _, js in outcome.items())
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            logger.info(json.dumps(outcome) if args.json else '%d%% success (%d pods on)' % (pct, dead))
            return 0 if pct == 100 else 1

    return _Tool()