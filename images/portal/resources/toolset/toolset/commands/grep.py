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
import json
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            '''
                Displays high-level information for the specified cluster(s).

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'grep'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='?', default='*', help='cluster(s) (can be a glob pattern, e.g foo*)')
            parser.add_argument('-j', '--json', action='store_true', help='switch for json output')

        def body(self, args, _, proxy):

            def _query(zk):
                replies = fire(zk, args.clusters, 'info')
                return len(replies), [[key, '|', hints['ip'], '|', hints['node'], '|', hints['process'], '|', hints['state']]
                                      for key, (_, hints, code) in sorted(replies.items()) if code == 200]

            total, js = run(proxy, _query)
            pct = ((len(js) * 100) / total) if total else 0
            if args.json:
                out = {item[0]: {'ip': item[2], 'node': item[4], 'process': item[6], 'state': item[8]} for item in js}
                logger.info(json.dumps(out))

            elif js:

                #
                # - justify & format the whole thing in a nice set of columns
                #
                logger.info('<%s> -> %d%% replies (%d pods total) ->\n' % (args.clusters, pct, len(js)))
                rows = [['pod', '|', 'pod IP', '|', 'node', '|', 'process', '|', 'state'], ['', '|', '', '|', '', '|', '', '|', '']] + js
                widths = [max(map(len, col)) for col in zip(*rows)]
                for row in rows:
                    logger.info('  '.join((val.ljust(width) for val, width in zip(row, widths))))

            return 0

    return _Tool()