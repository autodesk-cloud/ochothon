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
import pprint

from ochopod.core.fsm import diagnostic, spin_lock
from ochopod.core.utils import shell
from subprocess import Popen, PIPE
from toolset.poll import metrics, resources
from toolset.scale import scale

logger = logging.getLogger('ochopod')

def autoscale():

    #
    # - Incremental unit of resources.
    #
    unit = {
        'mem': 2,
        'cpus': 0.1,
        'instances': 1,
    }

    #
    # - Threshold of allocable resources. When computational resources are incremented
    # - to the limit, increment application instances.
    #
    lim = {
        'mem': 64,
        'cpus': 1,
        'instances': 5,
    }

def pulse(cluster='olivier.flask-sample'):

    #
    # - Pulse cluster up and down
    #
    i = 0

    while True:

        time.sleep(10.0)

        if i % 4 == 0:

            scale({cluster: {'instances' : 1, 'mem': 16, 'cpus' : 0.25}})

        elif i % 4 == 1 or i % 4 == 3:

            scale({cluster: {'instances' : 2, 'mem': 32, 'cpus' : 0.5}})

        elif i % 4 == 2:

            scale({cluster: {'instances' : 3, 'mem': 64, 'cpus' : 0.75}})

        i += 1

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

        pulse()

        # for i in range(10):
        #     time.sleep(10.0)
        #     pprint.pprint(metrics())
        #     pprint.pprint(resources('*system*'))

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % diagnostic(failure))

    finally:

        sys.exit(1)