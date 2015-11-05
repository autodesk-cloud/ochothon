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

from ochopod.core.fsm import diagnostic
from threading import Thread
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


class _Automation(Thread):

    def __init__(self, proxy, cluster, indices):
        super(_Automation, self).__init__()

        self.cluster = cluster
        self.out = \
            {
                'ok': False,
                'reset': []
            }
        self.proxy = proxy
        self.indices = indices

        self.start()

    def run(self):
        try:

            #
            # - first turn off the pods
            # - keep track of the indices
            #
            def _query(zk):
                replies = fire(zk, self.cluster, 'control/off', subset=self.indices)
                return [seq for _, (seq, _, code) in replies.items() if code == 200]

            pods = run(self.proxy, _query)

            #
            # - then turn those pod back on
            #
            def _query(zk):
                replies = fire(zk, self.cluster, 'control/on', subset=pods)
                return [seq for _, (seq, _, code) in replies.items() if code == 200]

            assert pods == run(self.proxy, _query), 'one or more pods failed to switch back on'

            self.out['reset'] = pods
            self.out['ok'] = True

        except AssertionError as failure:

            logger.debug('%s : failed to reset -> %s' % (self.cluster, failure))

        except Exception as failure:

            logger.debug('%s : failed to reset -> %s' % (self.cluster, diagnostic(failure)))

    def join(self, timeout=None):

        Thread.join(self)
        return self.out


def go():

    class _Tool(Template):

        help = \
            '''
                Switches the specified pods on/off/on (their sub-process being gracefully shutdown and restarted).
                Individual containers can also be cherry-picked by specifying their sequence index and using -i. Please
                note you must by default use -i and specify what containers to reset. If you want to reset multiple
                containers at once you must specify --force.

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'reset'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='+', help='clusters (can be a glob pattern, e.g foo*)')
            parser.add_argument('-i', '--indices', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('-j', action='store_true', dest='json', help='json output')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, unknown, proxy):

            assert args.force or args.indices, 'you must specify --force if -i is not set'

            #
            # - run the workflow proper (one thread per container definition)
            #
            threads = {cluster: _Automation(proxy, cluster, args.indices) for cluster in args.clusters}

            #
            # - wait for all our threads to join
            #
            n = len(threads)
            outcome = {key: thread.join() for key, thread in threads.items()}
            reset = sum(len(js['reset']) for _, js in outcome.items())
            pct = (100 * sum(1 for _, js in outcome.items() if js['ok'])) / n if n else 0
            logger.info(json.dumps(outcome) if args.json else '%d%% success (%d pods reset)' % (pct, reset))
            return 0 if pct == 100 else 1


    return _Tool()