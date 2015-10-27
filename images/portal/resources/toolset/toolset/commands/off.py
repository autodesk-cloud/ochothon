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
import logging

from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            '''
                Switches one or more containers off (their sub-process being gracefully shutdown while the pod keeps
                running). Individual containers can also be cherry-picked by specifying their sequence index and using
                -i. Please note you must by default use -i and specify what containers to turn off. If you want to turn
                multiple containers off at once you must specify --force.
            '''

        tag = 'off'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='+', help='clusters (can be a glob pattern, e.g foo*)')
            parser.add_argument('-i', '--indices', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, unknown, proxy):

            assert args.force or args.indices, 'you must specify --force if -i is not set'

            for token in args.clusters:

                def _query(zk):
                    replies = fire(zk, token, 'control/off', subset=args.indices)
                    return len(replies), [pod for pod, (_, _, code) in replies.items() if code == 200]

                total, js = run(proxy, _query)
                if js:
                    pct = (len(js) * 100) / total
                    logger.info('<%s> -> %d%% replies, %d pods off' % (token, pct, len(js)))

    return _Tool()