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

from ochopod.core.fsm import diagnostic
from toolset.poll import metrics, resources
from toolset.scale import scale

logger = logging.getLogger('ochopod')

def autoscale(clusters, period=300.0):
    """
        Scales the cluster automatically. One may set a unit of resources and the limit of 
        allocable resources as follows::

            #
            # - Incremental unit of resources.
            #
            unit = {
                'mem': 16,
                'cpus': 0.25,
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

        This particular example is meant to scale a cluster of pods with this config in its lifecycle::

            from random import choice

            checks = 3
            check_every = 10.0
            pipe_subprocess = True
            metrics = True

            def sanity_check(self, pid):
                
                #
                # - Randomly decide to be stressed  
                #
                return {'stressed': choice(['Very', 'Nope'])}

        General usage for this function:
        :param clusters: list of strings matching particular namespace/clusters for scaling
        :param period: period (secs) to wait before polling for metrics and scaling
    """

    unit = {
        'instances': 1,
    }   

    lim = {
        'instances': 6,
    }

    while True:

        time.sleep(period)
        
        for cluster in clusters:

            mets = metrics('%s*' % cluster)
            print 'Metrics for %s: %s' %(cluster, mets)
            stressed = sum(1 for key, item in mets.iteritems() if item['stressed'] == 'Very')

            if stressed > len(mets)/2.0 and len(mets) + unit['instances'] <= lim['instances']:

                    scale({cluster: {'instances': len(mets) + unit['instances']}})
            
            elif stressed < len(mets)/2.0 and len(mets) > unit['instances']:
                    
                    scale({cluster: {'instances': len(mets) - unit['instances']}})

def pulse(clusters, period=60.0):
    """
        Scales cluster up and down periodically
        :param clusters: list of strings matching particular namespace/clusters for scaling
        :param period: period (secs) between pulses
    """

    #
    # - Pulse cluster up and down
    #
    i = 0

    while True:

        time.sleep(period)

        for cluster in clusters:

            if i % 4 == 0:

                scale({cluster: {'instances': 1, 'mem': 16, 'cpus' : 0.25}})

            elif i % 4 == 1 or i % 4 == 3:

                scale({cluster: {'instances': 2, 'mem': 32, 'cpus' : 0.5}})

            elif i % 4 == 2:

                scale({cluster: {'instances': 3, 'mem': 64, 'cpus' : 0.75}})

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
        
        #
        # - Check for passed set of scalee clusters in deployment yaml
        #
        clusters = []
        if 'SCALEES' in env:
            clusters = env['SCALEES'].split(',')

        # Use our very simple autoscaling routine
        autoscale(clusters, 30.0)

    except Exception as failure:

        logger.fatal('unexpected condition -> %s' % failure)

    finally:

        sys.exit(1)