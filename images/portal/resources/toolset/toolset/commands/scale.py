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
import os
import fnmatch
from ochopod.core.fsm import diagnostic
from ochopod.core.utils import retry
from random import choice
from requests import get, put, delete
from toolset.io import fire, run, ZK
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def go():

    class _Tool(Template):

        help = \
            """
                Tool for scaling a set of scalee apps running under Ochopod and Marathon. Note that this function is a scale-to, not a scale-by.

                Usage example::
                    > scale *this-cluster* *that-cluster* -i 3

            """

        tag = 'scale'

        def customize(self, parser):

            parser.add_argument('clusters', nargs='*', type=str, help='1+ clusters (can be a glob pattern, e.g foo*, but must match only one cluster to avoid clashing).')           
            parser.add_argument('-i', '--instances', type=int, help='Number of instances to scale to for all clusters provided.')
            parser.add_argument('-j', '--json', action='store_true', help='switch for json output')
            parser.add_argument('-t', '--timeout', action='store', dest='timeout', type=int, default=60, help='timeout in seconds')

        def body(self, args, proxy):

            #
            # - we need to pass the framework master IPs around (ugly)
            # - Get marathon data
            #
            assert 'MARATHON_MASTER' in os.environ, "$MARATHON_MASTER not specified (check portal's pod)"
            master = choice(os.environ['MARATHON_MASTER'].split(','))
            headers = \
                {
                    'content-type': 'application/json',
                    'accept': 'application/json'
                }

            #
            # - Get ochopod data: dict of cluster/namespace to application id
            #
            def _query(zk):
                replies = fire(zk, '*', 'info')
                return len(replies), {key.rstrip(' .#%s' % index): hints['application'] for key, (index, hints, code) in replies.items() if code == 200}

            _, ocho_data = run(proxy, _query, args.timeout)

            #
            # - Hold function to wait on Marathon while it is deploying a task
            #
            @retry(timeout=args.timeout, pause=2)
            def _marathon_hold(name):
                reply = get('http://%s/v2/deployments' % master)
                code = reply.status_code
                js = json.loads(reply.text)
                assert code == 200 or code == 201, "Marathon deployment GET failed (HTTP %d)" % code
                assert js == [], "Marathon didn't finish deploying yet for %s" % name
                return js

            #
            # - For json output
            #
            outs = {}

            #
            # - Go through all provided glob patterns
            #
            for cluster in args.clusters:

                #
                # - Check keys for overlaps and warn
                #
                filtered = fnmatch.filter(args.clusters, cluster).remove(cluster)

                if not filtered is None and not args.json:

                    logger.warning('Cluster %s may overlap with %s', cluster, filtered.join(', '))

                #
                # - Go through each namespace/cluster key and specification pair and send request
                # - to the Marathon endpoint. 
                #
                for name in set(fnmatch.filter(ocho_data.keys(), cluster)):

                    try:

                        assert args.instances, 'Missing target number of instances for scaling (-i flag).'

                        #
                        # - Get the specs for the current app that matches the requested namespace/cluster
                        #    
                        mara_data = get('http://%s/v2/apps/%s' % (master, ocho_data[name]))
                        code = mara_data.status_code
                        assert code == 200 or code == 201, "Could not scale: Marathon couldn't find the correct app id for %s (HTTP %d)" % (name, code)
                        curr = json.loads(mara_data.text)['app']

                        #
                        # - Scale instance # down. Need to gracefully kill ochopods before telling Marathon to kill 
                        # - the corresponding tasks.
                        #
                        if curr['instances'] > args.instances:

                            assert args.instances >= 0, "Could not scale: Invalid scaling instance number (%d) for %s" % (args.instances, name)
                            delta = curr['instances'] - args.instances

                            #
                            # - Sort marathon task data by started time and slice off the older tasks (scale down newer instances)
                            #
                            victims = sorted(curr['tasks'], key=(lambda x: x['startedAt']))[args.instances:]
                                                                                                                                                                                                    
                            def _query(zk):
                                replies = fire(zk, name, 'info')                                                                                                                                    
                                return {hints['task']: index for key, (index, hints, code) in replies.items() if code == 200}                                                                       
                            
                            js = run(proxy, _query, args.timeout)
                                                                                                                                                                                                    
                            #
                            # - get indeces of tasks to be killed                                                                                                                                   
                            #
                            subset = [js[victim['id']] for victim in victims]
                            
                            #
                            # - Wrapper to kill all (or part of) the pods using a POST /control/kill
                            # - wait for them to be dead
                            # - warning, /control/kill will block (hence the 5 seconds timeout)
                            #
                            @retry(timeout=args.timeout, pause=0)
                            def _kill(name, subset):
                                def _query(zk):
                                    replies = fire(zk, name, 'control/kill', subset=subset, timeout=args.timeout)
                                    return [(code, seq) for seq, _, code in replies.values()]

                                #
                                # - fire the request to one or more pods
                                # - wait for every pod to report back a HTTP 410 (GONE)
                                # - this means the ochopod state-machine is now idling (e.g dead)
                                #
                                js = run(proxy, _query)
                                gone = sum(1 for code, _ in js if code == 410)
                                assert gone == len(js), 'at least one pod is still running'
                                return [seq for _, seq in js]

                            #   
                            # - Kill the subset of pods
                            #                                                                                                                                                                       
                            down = _kill(name, subset)
                            assert down, 'Could not scale: The pods under %s did not die' % name

                            #
                            # - Wrapper to retry deleting tasks on Marathon; this is important to prevent Ochopod from
                            # - desyncing with Marathon during scale down requests.
                            #
                            @retry(timeout=args.timeout, pause=2)
                            def _del(url):
                                reply = delete(url)
                                code = reply.status_code
                                assert code == 200 or code == 201, "Marathon task DELETE submission failed (HTTP %d)" % code

                            #
                            # - Tell marathon to delete and scale each task corresponding to the dead pods
                            #
                            for victim in victims:

                                _del('http://%s/v2/apps/%s/tasks/%s?scale=true' % (master, ocho_data[name], victim['id']))

                                if not _marathon_hold(name) == [] and not args.json:

                                    logger.warning('Marathon timed out during deployment for %s' % name)

                        #
                        # - Wrapper to retry specifically if a 409 conflict code occurs when PUTting to the app ID endpoint
                        # - this occurs if Marathon is queried during deployment of a previous spec
                        #
                        @retry(timeout=args.timeout, pause=2)
                        def _put(app, spec):
                            reply = put('http://%s/v2/apps/%s' % (master, app), data=json.dumps(spec), headers=headers)
                            code = reply.status_code
                            assert code == 200 or code == 201, 'Could not scale: PUT submission conflicted (HTTP %d) for %s' % (code, name)
                            return code

                        #
                        # - Send the actual scale request; if scaling up, we didn't need to touch ochopod
                        # - if scaling down, Marathon still requires this request to be sent after the DELETEs above
                        #
                        code = _put(ocho_data[name], {'instances': args.instances})
                        assert code == 200 or code == 201, 'Could not scale: PUT submission failed (HTTP %d) for %s' % (code, name)

                        if not _marathon_hold(name) == [] and not args.json:

                            logger.warning('Marathon timed out during deployment for %s' % name)
                        
                        #
                        # - Wrapper to wait for pods to be in a mode specified in target
                        #
                        @retry(timeout=args.timeout, pause=2, default={})
                        def _spin(name, target, num):
                            def _query(zk):
                                replies = fire(zk, name, 'info')
                                return [(hints['process'], seq) for seq, hints, _ in replies.values()
                                        if hints['application'] == ocho_data[name] and hints['process'] in target]

                            js = run(proxy, _query)
                            assert len(js) == num, 'not all pods running yet'
                            return js

                        #
                        # - wait for all the pods to be in the 'running' mode
                        #
                        js = _spin(name, ['running'], args.instances)
                        running = sum(1 for state, _ in js if state is not 'dead')
                        
                        #
                        # - output
                        #
                        if args.json:

                            outs[name] = {'running': running, 'requested': args.instances}
                        
                        elif running == args.instances:

                            logger.info('Scaled: %d/%d pods are running under %s' % (running, args.instances, name))

                        else:

                            logger.warning('Could not scale: %d/%d pods are running under %s' % (running, args.instances, name))

                    except Exception as e:
                        
                        if args.json:
                            
                            outs[name] = {'failed': diagnostic(e)}

                        else:

                            logger.warning('Could not scale %s for %s: failure %s' % (name, cluster, diagnostic(e)))
                        
            if args.json:

                logger.info(json.dumps(outs))

    return _Tool()
