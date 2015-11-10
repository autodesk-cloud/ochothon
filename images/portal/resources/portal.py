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
import hashlib
import hmac
import json
import logging
import ochopod
import os
import sys
import tempfile
import time
import shutil

from flask import Flask, request
from ochopod.core.fsm import diagnostic
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

            out = []
            ok = False
            ts = time.time()
            tmp = tempfile.mkdtemp()
            try:

                #
                # - retrieve the command line
                #
                assert 'X-Shell' in request.headers, 'X-Shell header missing'
                line = request.headers['X-Shell']

                #
                # - compute the incoming command line HMAC and compare (use our pod token as the key)
                #
                if 'token' in os.environ and os.environ['token']:
                    assert 'X-Signature' in request.headers, 'signature missing (make sure you define $OCHOPOD_TOKEN)'
                    digest = 'sha1=' + hmac.new(os.environ['token'], line, hashlib.sha1).hexdigest()
                    assert digest == request.headers['X-Signature'], 'SHA1 signature mismatch (check your token)'

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
                logger.debug('http -> shell request "%s"' % line)
                pid = Popen('toolset %s' % line, shell=True, stdout=PIPE, stderr=None, env=env, cwd=tmp)

                #
                # - pipe the process stdout
                # - return as json ('out' contains the verbatim dump from the sub-process stdout)
                #
                while 1:
                    code = pid.poll()
                    line = pid.stdout.readline()
                    if not line and code is not None:
                        break
                    elif line:
                        out += [line.rstrip('\n')]

                ok = pid.returncode == 0

            except AssertionError as failure:

                out = ['failure -> %s' % failure]

            except Exception as failure:

                out = ['unexpected failure -> %s' % diagnostic(failure)]

            finally:

                #
                # - make sure to cleanup our temporary directory
                #
                shutil.rmtree(tmp)

            ms = 1000 * (time.time() - ts)
            js = \
                {
                    'ok': ok,
                    'ms': ms,
                    'out': '\n'.join(out)
                }

            return json.dumps(js), 200, \
                {
                    'Content-Type': 'application/json; charset=utf-8'
                }

        #
        # - run our flask endpoint on TCP 9000
        #
        web.run(host='0.0.0.0', port=9000, threaded=True)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)