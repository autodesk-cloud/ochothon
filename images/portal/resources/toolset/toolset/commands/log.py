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
                Dumps the internal ochopod log for the specified cluster(s).
            '''

        tag = 'log'

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs='*', default='*', help='1+ clusters (can be a glob pattern, e.g foo*)')

        def body(self, args, proxy):

            for token in args.clusters:

                def _query(zk):
                    replies = fire(zk, token, 'log')
                    return {key: log for key, (_, log, code) in replies.items() if code == 200}

                js = run(proxy, _query)
                if js:
                    pct = (len(js) * 100) / len(js)
                    unrolled = ['- %s\n%s\n' % (key, '\n  '.join(log[-64:])) for key, log in js.items()]
                    logger.info('<%s> -> %d%% replies (%d pods total) ->\n%s' % (token, pct, len(js), '\n'.join(unrolled)))


    return _Tool()