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
from toolset.io import fire, run, ZK
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            """
                Polls and returns the metrics gathered during sanity checks.

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            """

        tag = 'poll'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='?', default='*', help='cluster(s) (can be a glob pattern, e.g foo*)')
            parser.add_argument('-j', '--json', action='store_true', help='switch for json output')

        def body(self, args, _, proxy):

            def _query(zk):
                replies = fire(zk, args.clusters[0], 'info')
                return len(replies), {key: hints['metrics'] for key, (index, hints, code) in replies.items() if code == 200 and 'metrics' in hints}

            total, js = run(proxy, _query)
            pct = ((len(js) * 100) / total) if total else 0
            if args.json:
                logger.info(json.dumps(js))

            elif js:

                logger.info('%d pods, %d%% replies ->\n' % (len(js), pct))
                rows = [['pod', '|', 'metrics'], ['', '|', '']] + sorted([[key, '|', json.dumps(val)] for key, val in js.iteritems()])
                widths = [max(map(len, col)) for col in zip(*rows)]
                for row in rows:
                    logger.info('  '.join((val.ljust(width) for val, width in zip(row, widths))))

            return 0

    return _Tool()
