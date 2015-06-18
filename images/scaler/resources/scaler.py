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

from ochopod.core.fsm import diagnostic, spin_lock
from ochopod.core.utils import shell
from subprocess import Popen, PIPE
from toolset.poll import poll

logger = logging.getLogger('ochopod')

if __name__ == '__main__':

    try:

        #
        # - parse our ochopod hints
        # - enable CLI logging
        # - pass down the ZK ensemble coordinate
        #
        # env = os.environ
        # hints = json.loads(env['ochopod'])
        # ochopod.enable_cli_log(debug=hints['debug'] == 'true')
        # env['OCHOPOD_ZK'] = hints['zk']

        for i in range(10):
            print poll()
            time.sleep(10.0)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)