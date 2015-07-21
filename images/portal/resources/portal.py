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
import ochopod
import os
import pykka
import sys
import tempfile
import time
import shutil

from flask import Flask, request, render_template
from ochopod.core.fsm import diagnostic, spin_lock
from ochopod.core.utils import shell
from os.path import join
from subprocess import Popen, PIPE


logger = logging.getLogger('ochopod')
web = Flask(__name__)


if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - pass down the ZK ensemble coordinate
        #
        env = os.environ
        hints = json.loads(env['ochopod'])
        ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        env['OCHOPOD_ZK'] = hints['zk']

        @web.route('/shell', methods=['POST'])
        def _from_curl():
            tmp = tempfile.mkdtemp()
            try:

                #
                # - download each multi-part file to a temporary folder
                #
                for tag, upload in request.files.items():
                    where = join(tmp, tag)
                    logger.debug('http -> upload @ %s' % where)
                    upload.save(where)

                #
                # - get the shell snippet to run from the X-Shell header
                # - use the 'toolset' python package that's installed in the container
                # - open it
                #
                ts = time.time()
                line = request.headers['X-Shell']
                logger.debug('http -> shell request "%s"' % line)

                #
                # - pipe the process stdout
                # - return as json ('out' contains the verbatim dump from the sub-process stdout)
                #
                outs = []
                pid = Popen('toolset %s' % line, shell=True, stdout=PIPE, stderr=PIPE, env=env, cwd=tmp)
                while True:

                    line = pid.stdout.readline().rstrip('\n')
                    code = pid.poll()
                    if line == '' and code is not None:
                        break
                    outs += [line]

                ms = 1000 * (time.time() - ts)
                return json.dumps({'ok': pid.returncode == 0, 'ms': int(ms), 'out': '\n'.join(outs)})

            except Exception as failure:

                why = diagnostic(failure)
                logger.warning('unexpected failure -> %s' % why)
                return json.dumps({'ok': False, 'out': 'unexpected failure -> %s' % why})

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

        @web.route('/shell', methods=['GET'])
        def _from_web_shell():
            tmp = tempfile.mkdtemp()
            try:

                #
                # - get the shell snippet from the uri
                # - use the 'toolset' python package that's installed in the container
                # - open it
                #
                ts = time.time()
                line = request.args.get('line', 0, type=str)
                logger.debug('http -> shell request "%s"' % line)
                pid = Popen('toolset %s' % line, shell=True, stdout=PIPE, stderr=PIPE, env=env, cwd=tmp)

                #
                # - wait for completion
                # - return as json ('out' contains the verbatim dump from the sub-process stdout)
                #
                outs = []

                #
                # - taken from ochopod's subprocess piping; avoids issues with buffering
                #
                while True:

                    line = pid.stdout.readline().rstrip('\n')
                    code = pid.poll()
                    if line == '' and code is not None:
                        break
                    outs += [line]

                ms = 1000 * (time.time() - ts)
                return json.dumps({'ok': pid.returncode == 0, 'ms': int(ms), 'out': '\n'.join(outs)})

            except Exception as failure:

                why = diagnostic(failure)
                logger.warning('unexpected failure -> %s' % why)
                return json.dumps({'ok': False, 'out': 'unexpected failure -> %s' % why})

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

        @web.route('/')
        def index():

            #
            # - index.html contains all the jquery magic that will run the shell and
            #   use ajax to I/O with us
            #
            return render_template('index.html')

        #
        # - run our flask endpoint on TCP 9000
        #
        web.run(host='0.0.0.0', port=9000, threaded=True)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)