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
                Displays a breakdown of how pods have been allocated to nodes. The load is the percentage of pods
                running on one given node.
            '''

        tag = 'nodes'

        def body(self, args, proxy):

            def _query(zk):
                replies = fire(zk, '*', 'info')
                return len(replies), [hints['node'] for _, (_, hints, code) in replies.items() if code == 200]

            total, js = run(proxy, _query)
            if js:

                rollup = {key: 0 for key in set(js)}
                for node in js:
                    rollup[node] += 1

                pct = (100 * len(js)) / total
                logger.info('%d pods, %d%% replies ->\n' % (len(js), pct))
                unrolled = [[key, '|', '%d%%' % ((100 * n) / total)] for key, n in sorted(rollup.items())]
                rows = [['node', '|', 'load'], ['', '|', '']] + unrolled
                widths = [max(map(len, col)) for col in zip(*rows)]
                for row in rows:
                    logger.info('  '.join((val.ljust(width) for val, width in zip(row, widths))))

    return _Tool()