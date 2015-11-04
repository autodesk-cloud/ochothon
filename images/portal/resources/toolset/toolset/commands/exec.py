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

from os import path
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            '''
                Invokes the specified tool on zero or more pods. Tools are defined on a per-pod basis and are used
                to customize and add extra functionality (debugging, cleanup, maintenance...). The command line will
                be passed to the receiving pods and parsed allowing the define special switches and options. Any file
                specified on the command line in the CLI will be uploaded to the pod in a temporary directory. Please
                note the -i, -d, -h, --indices and --force switches will be preempted and thus cannot be used by
                the tools (e.g if you need to expose a debug switch use something like --debug). Make sure to use the
                -t option to specify a reasonable timeout if you plan on running slow operations (default of 1 minute).

                By default pods do not expose any tool.

                Individual containers can also be cherry-picked by specifying their sequence index and using -i.
                Please note you must by default use -i and specify what containers to reset. If you want to reset
                multiple containers at once you must specify --force.

                This tool supports optional output in JSON format for 3rd-party integration via the -j switch.
            '''

        tag = 'exec'

        strict = False

        def customize(self, parser):

            parser.add_argument('clusters', type=str, nargs=1, help='clusters on which to invoke the specified tool (can be a glob pattern, e.g foo*)')
            parser.add_argument('cmdline', type=str, nargs='+', help='tool command line (e.g foo bar.yml)')
            parser.add_argument('-i', '--indices', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('-j', '--json', action='store_true', help='switch for json output')
            parser.add_argument('-t', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, unknown, proxy):

            assert args.force or args.indices, 'you must specify --force if -i is not set'

            if unknown is not None:
                args.cmdline += unknown

            files = {}
            headers = {'X-Shell': ' '.join(args.cmdline)}
            for token in args.cmdline:
                if path.isfile(token):
                    with open(token, 'rb') as f:
                        files[token] = f.read()

            def _query(zk):
                replies = fire(zk, args.clusters[0], 'exec', subset=args.indices, headers=headers, files=files, timeout=args.timeout)
                return len(replies), {key: js for key, (_, js, code) in replies.items() if code == 200}

            total, js = run(proxy, _query)
            if js and not args.json:

                pct = ((len(js) * 100) / total)
                logger.info('<%s> -> %d%% replies (%d pods total) ->\n' % (args.clusters[0], pct, len(js)))
                for key, log in js.items():
                    suffix = '\n\n %s\n' % '\n '.join(log['stdout']) if log['stdout'] else ''
                    logger.info('- %s (exit code %d)%s' % (key, log['code'], suffix))

            if args.json:
                logger.info(json.dumps(js))

    return _Tool()