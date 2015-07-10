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
import os
from toolset.io import fire, run, ZK
from random import choice
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            """
                Tool for polling ochopod cluster for metrics returned during sanity_checks.
            """

        tag = 'poll'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='*', default='*', help='1+ clusters (can be a glob pattern, e.g foo*).')
            parser.add_argument('-j', '--json', action='store_true', help='switch for json output')
            parser.add_argument('-t', '--timeout', action='store', dest='timeout', type=int, default=20, help='timeout in seconds (default 20)')

        def body(self, args, proxy):

            #
            # - Grab user defined metrics returned in sanity_check()s
            #
            outs = {}

            for token in args.clusters:

                def _query(zk):
                    replies = fire(zk, token, 'info')
                    return len(replies), {key: hints['metrics'] for key, (index, hints, code) in replies.items() if 
                        code == 200 and 'metrics' in hints}

                total, js = run(proxy, _query, args.timeout)
                
                outs.update(js)

                #
                # - Prettify if not asked for a json string
                #
                if not args.json:

                    pct = (len(js) * 100) / total
                    logger.info('<%s> -> User-defined metrics ->\n' % token)
                    rows = [['pod', '|', 'metrics'], ['', '|', '']] + [[key, '|', json.dumps(val)] for key, val in js.iteritems()]
                    widths = [max(map(len, col)) for col in zip(*rows)]
                    for row in rows:
                        logger.info('  '.join((val.ljust(width) for val, width in zip(row, widths))))
            
            if args.json:

                logger.info(json.dumps(outs))

    return _Tool()
