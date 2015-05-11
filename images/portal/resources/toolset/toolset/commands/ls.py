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

from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            '''
                Lists all the ochopod cluster(s) currently active. The number of containers that are tagged as running
                is indicated as well as the optional status status line.

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'ls'

        def customize(self, parser):

            parser.add_argument('-j', action='store_true', dest='json', help='json output')

        def body(self, args, proxy):

            def _query(zk):
                replies = fire(zk, '*', 'info')
                return len(replies), {key: hints for key, (_, hints, code) in replies.items() if code == 200}

            total, js = run(proxy, _query)
            if js:

                out = {}
                for key, hints in js.items():
                    qualified = key.split(' ')[0]
                    if not qualified in out:
                        out[qualified] = \
                            {
                                'total': 0,
                                'running': 0,
                                'status': ''
                            }

                    item = out[qualified]
                    item['total'] += 1
                    if hints['process'] == 'running':
                        item['running'] += 1

                    if 'status' in hints and hints['status']:
                        item['status'] = hints['status']

                if args.json:
                    logger.info(json.dumps(out))

                else:
                    pct = (100 * len(js)) / total
                    logger.info('%d pods, %d%% replies ->\n' % (len(js), pct))
                    unrolled = [[key, '|', '%d/%d' % (item['running'], item['total']), '|', item['status']] for key, item in sorted(out.items())]
                    rows = [['cluster', '|', 'ok', '|', 'status'], ['', '|', '', '|', '']] + unrolled
                    widths = [max(map(len, col)) for col in zip(*rows)]
                    for row in rows:
                        logger.info('  '.join((val.ljust(width) for val, width in zip(row, widths))))

    return _Tool()