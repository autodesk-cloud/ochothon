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
import fnmatch
import pprint
from ochopod.core.utils import merge
from toolset.io import fire, run, ZK
from requests import get
from random import choice
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            """
                Tool for polling ochopod cluster for metrics returned during sanity_checks, or for polling mesos masters for 
                available and unavailable resources. Equivalent to a call to mesos's /metrics/snapshot endpoint.  
            """

        tag = 'poll'

        def customize(self, parser):

            parser.add_argument('-c', '--clusters', type=str, nargs='*', default='*', help='1+ clusters (can be a glob pattern, e.g foo*).')
            parser.add_argument('-m', '--mode', type=str, default='metrics', choices=['metrics', 'marathon'], help='Polling target may either be metrics or Marathon.')
            parser.add_argument('-r', '--regex', type=str, default='*', help='Regex by which Marathon data keys are filtered.')
            parser.add_argument('-t', '--timeout', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')

        def body(self, args, proxy):

            if args.mode == 'metrics':

                #
                # - Grab user defined metrics returned in sanity_check()s
                #
                for token in args.clusters:

                    def _query(zk):
                        replies = fire(zk, token, 'info')
                        return len(replies), {key: hints['metrics'] for key, (index, hints, code) in replies.items() if 
                            code == 200 and 'metrics' in hints}

                    _, js = run(proxy, _query, args.timeout)
                    
                    logger.info(pprint.pformat(js))

            elif args.mode == 'marathon':

                #
                # - Use the same master for the mesos stats and metrics endpoints. 
                #
                assert 'MARATHON_MASTER' in os.environ, "$MARATHON_MASTER not specified (check portal pod)"
                master = choice(os.environ['MARATHON_MASTER'].split(',')).split(':')[0]
                reply = get('http://%s:5050/metrics/snapshot' % master)
                code = reply.status_code
                assert code == 200 or code == 201, 'mesos /metrics/snapshot request failed (HTTP %d)... is Mesos >= 0.19.0?' % code
                stats = get('http://%s:5050/stats.json' % master)
                code = stats.status_code
                assert code == 200 or code == 201, 'mesos /stats.json request failed (HTTP %d)... is Mesos >= 0.19.0?' % code

                #
                # - Load the json response, merge, then filter by provided regex.
                #
                data = merge(json.loads(reply.text), json.loads(stats.text))
                data = dict(filter(lambda x: fnmatch.fnmatch(x[0], args.regex), [[key, val] for key, val in data.iteritems()]))
                logger.info(pprint.pformat(data))


    return _Tool()
