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
from io import fire, run, ZK

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def poll(regex='*', timeout=60.0):
    """
        Tool for polling ochopod cluster for metrics.

        :param regex: a str to match against namespace/cluster keys for retrieving metrics.
        :param timeout: float amount of seconds allowed for sending the poll request.    
    """

    def _query(zk):
        replies = fire(zk, '*', 'info')
        return len(replies), dict((key, hints['metrics']) for key, (index, hints, code) in replies.items() if 
            code == 200 and 'metrics' in hints and fnmatch.fnmatch(key, regex))

    proxy = ZK.start([node for node in os.environ['OCHOPOD_ZK'].split(',')])

    _, js = run(proxy, _query, timeout)
    
    return js