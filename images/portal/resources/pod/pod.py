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
import os
import time

from ochopod.bindings.generic.marathon import Pod
from ochopod.core.utils import shell
from ochopod.models.piped import Actor as Piped

logger = logging.getLogger('ochopod')


if __name__ == '__main__':

    #
    # - use an optional token to perform SHA1 digest verification
    # - this token can be defined via the $OCHOPOD_TOKEN environment variable
    #
    token = os.environ['ochopod_token'] if 'ochopod_token' in os.environ else ''

    class Strategy(Piped):

        cwd = '/opt/portal'
        
        check_every = 60.0

        pid = None

        since = 0.0

        def sanity_check(self, pid):

            #
            # - simply use the provided process ID to start counting time
            # - this is a cheap way to measure the sub-process up-time
            #
            now = time.time()
            if pid != self.pid:
                self.pid = pid
                self.since = now

            lapse = (now - self.since) / 3600.0

            return \
                {
                    'token': token,
                    'uptime': '%.2f hours (pid %s)' % (lapse, pid)
                }

        def configure(self, _):

            #
            # - dig master.mesos
            # - this should give us a list of internal master IPs
            # - please note this will only work if mesos-dns has been setup (and is running)
            #
            _, lines = shell('dig master.mesos +short')
            if lines:
                masters = ','.join(['%s:8080' % line for line in lines])

            #
            # - no mesos-dns running ?
            # - if so $MARATHON_MASTER must be defined (legacy behavior)
            #
            else:
                assert 'MARATHON_MASTER' in os.environ, 'failed to look mesos-dns up and no $MARATHON_MASTER defined'
                masters = os.environ['MARATHON_MASTER']

            #
            # - run the webserver
            # - don't forget to pass the secret token as an environment variable
            #
            logger.debug('$MARATHON_MASTER=%s' % masters)
            return 'python portal.py', \
                   {
                       'token': token,
                       'MARATHON_MASTER': masters
                   }

    Pod().boot(Strategy)