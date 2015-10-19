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
                Runs a shell snippet across the specified cluster(s). Individual containers can also be cherry-picked
                by specifying their sequence index and using -i. Please note you must by default use -i and specify
                what containers to reset. If you want to reset multiple containers at once you must specify --force.
            '''

        tag = 'shell'

        def customize(self, parser):

            parser.add_argument('snippet', type=str, nargs=1, help='shell snippet to execute')
            parser.add_argument('clusters', type=str, nargs='*', default='*', help='1+ clusters (can be a glob pattern, e.g foo*)')
            parser.add_argument('-i', '--indices', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, proxy):

            assert args.force or args.indices, 'you must specify --force if -i is not set'

            for token in args.clusters:

                def _query(zk):
                    replies = fire(zk, token, 'shell', subset=args.indices, headers={'X-Shell': args.snippet[0]})
                    return len(replies), {key: js for key, (_, js, code) in replies.items() if code == 200}

                total, js = run(proxy, _query)
                if js:
                    pct = ((len(js) * 100) / total)
                    unrolled = ['- %s (exit code %d)\n\n  %s\n' % (key, log['code'], '\n  '.join(log['stdout'])) for key, log in js.items()]
                    logger.info('<%s> -> %d%% replies (%d pods total) ->\n%s' % (token, pct, len(js), '\n'.join(unrolled)))

    return _Tool()