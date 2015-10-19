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

from os import path
from toolset.io import fire, run
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():

    class _Tool(Template):

        help = \
            '''
                Upload a local file to one or more containers. By default the file will be uploaded to / but you can
                specify a target path by using -w. Make sure this path maps to an actual directory otherwise the
                operation will fail.

                Individual containers can also be cherry-picked by specifying their sequence index and using -i.
                Please note you must by default use -i and specify what containers to reset. If you want to reset
                multiple containers at once you must specify --force.
            '''

        tag = 'put'

        def customize(self, parser):

            parser.add_argument('file', type=str, nargs=1, help='local file to upload, e.g foo.txt')
            parser.add_argument('clusters', type=str, nargs='*', default='*', help='1+ clusters (can be a glob pattern, e.g foo*)')
            parser.add_argument('-i', '--indices', action='store', dest='indices', type=int, nargs='+', help='1+ indices')
            parser.add_argument('-w', '--where', action='store', dest='where', type=str, default='/', help='optional target directory')
            parser.add_argument('--force', action='store_true', dest='force', help='enables wildcards')

        def body(self, args, proxy):

            assert args.force or args.indices, 'you must specify --force if -i is not set'
            assert path.isfile(args.file[0]), '%s not found (ochothon bug ?)' % args.file[0]

            with open(args.file[0], 'rb') as f:

                for token in args.clusters:

                    def _query(zk):

                        headers = {'X-Path': args.where}
                        files = {args.file[0]: f.read()}
                        replies = fire(zk, token, 'upload', subset=args.indices, headers=headers, files=files)

                        return len(replies), [pod for pod, (_, _, code) in replies.items() if code == 200]

                    total, js = run(proxy, _query)
                    if js:
                        pct = ((len(js) * 100) / total)
                        logger.info('<%s> -> %d%% replies (%d pods total)' % (token, pct, len(js)))

    return _Tool()