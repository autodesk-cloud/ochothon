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
from ochopod.core.utils import merge
from io import fire, run, ZK
from requests import get
from random import choice

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def metrics(proxy, regex='*', timeout=60.0):
    """
        Tool for polling ochopod cluster for metrics returned during sanity_checks.

        :param regex: a str to match against namespace/cluster keys for retrieving metrics.
        :param timeout: float amount of seconds allowed for sending the poll request.    
    """

    def _query(zk):
        replies = fire(zk, regex, 'info')
        return len(replies), {key: hints['metrics'] for key, (index, hints, code) in replies.items() if 
            code == 200 and 'metrics' in hints}

    _, js = run(proxy, _query, timeout)
    
    return js

def resources(regex='*'):
    """
        Tool for polling mesos masters for available and unavailable resources. Equivalent to a call
        to mesos's /metrics/snapshot endpoint.  
    """

    #
    # - Use the same master for the mesos stats and metrics endpoints. 
    #
    assert 'MARATHON_MASTER' in os.environ, "$MARATHON_MASTER not specified (check scaler's pod.py)"
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
    data = dict(filter(lambda x: fnmatch.fnmatch(x[0], regex), [[key, val] for key, val in data.iteritems()]))
    return data
