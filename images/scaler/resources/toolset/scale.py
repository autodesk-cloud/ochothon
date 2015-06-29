import json
import logging
import os
import fnmatch
from ochopod.core.utils import retry
from random import choice
from requests import get, put, delete
from io import fire, run, ZK

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def scale(scalees={}, timeout=60.0):
    """
        Tool for scaling a set of scalee apps running under Ochopod and Marathon using a dict of specifications. Note that
        this function is a _scale-to_, not a scale-by.

        E.g., you may use::

            scalees = {
                '<namespace>.<cluster>': {
                    'instances': 5,
                    'mem': 32.0
                }
            }
            
        Scaling parameters include: 'instances', 'mem', 'cpus'.

        :param scalees: a dict mapping a cluster/namespace key to a secondary dict of specifications, according to which
        the corresponding app will be scaled.
        :param timeout: float amount of seconds allowed for scaling each namespace/cluster in scalees.    
    """

    #
    # - we need to pass the framework master IPs around (ugly)
    # - Get marathon data
    #
    assert 'MARATHON_MASTER' in os.environ, "$MARATHON_MASTER not specified (check scaler's pod.py)"
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

    proxy = ZK.start([node for node in os.environ['OCHOPOD_ZK'].split(',')])

    _, ocho_data = run(proxy, _query, timeout)

    #
    # - Hold function to wait on Marathon while it is deploying a task
    #
    @retry(timeout=timeout, pause=2)
    def _marathon_hold(name):
        reply = get('http://%s/v2/deployments' % master)
        code = reply.status_code
        js = json.loads(reply.text)
        assert code == 200 or code == 201, "Marathon deployment GET failed (HTTP %d)" % code
        assert js == [], "Marathon didn't finish deploying yet for %s" % name
        return js

    #
    # - Wrapper to retry _specifically_ if a 409 conflict code occurs when PUTting to the app ID endpoint
    # - this occurs if Marathon is queried during deployment of a previous spec
    #
    @retry(timeout=timeout, pause=2)
    def _put(app, spec):
        reply = put('http://%s/v2/apps/%s' % (master, app), data=json.dumps(spec), headers=headers)
        code = reply.status_code
        assert code != 409, 'Could not scale: PUT submission conflicted (HTTP %d) for %s' % (code, name)
        return code

    #
    # - Wrapper to wait for pods to be in a mode specified in target
    #
    @retry(timeout=timeout, pause=2, default={})
    def _spin(name, target, num):
        def _query(zk):
            replies = fire(zk, name, 'info')
            return [(hints['process'], seq) for seq, hints, _ in replies.values()
                    if hints['application'] == ocho_data[name] and hints['process'] in target]

        js = run(proxy, _query)
        assert len(js) == num, 'not all pods running yet'
        return js

    #
    # - Wrapper to kill all (or part of) the pods using a POST /control/kill
    # - wait for them to be dead
    # - warning, /control/kill will block (hence the 5 seconds timeout)
    #
    @retry(timeout=timeout, pause=0)
    def _kill(name, subset):
        def _query(zk):
            replies = fire(zk, name, 'control/kill', subset=subset, timeout=timeout)
            return [(code, seq) for seq, _, code in replies.values()]

        #
        # - fire the request one or more pods
        # - wait for every pod to report back a HTTP 410 (GONE)
        # - this means the ochopod state-machine is now idling (e.g dead)
        #
        js = run(proxy, _query)
        gone = sum(1 for code, _ in js if code == 410)
        assert gone == len(js), 'at least one pod is still running'
        return [seq for _, seq in js]

    #
    # - Check keys for overlaps and warn
    #
    for name in scalees.keys():
        filtered = fnmatch.filter(scalees.keys(), name).remove(name)
        if not filtered is None:
            logger.warning('Key %s in scalees dict may overlap with %s', name, filtered.join(', '))

    #
    # - Go through each provided namespace/cluster key and specification pair and send request
    # - to the Marathon endpoint. 
    #
    for name, spec in scalees.iteritems():

        try:

            #
            # - Get pods corresponding to namespace/cluster... we only allow one cluster per scalees key for now
            # - Regex support may be implemented later
            #
            filtered = set(fnmatch.filter(ocho_data.keys(), name))
            assert len(filtered) < 2, 'Could not scale: Found multiple clusters under %s' % name
            assert len(filtered) > 0, 'Could not scale: No clusters found under %s ' % name
            name = filtered.pop()

            #
            # - Get the specs for the current app that matches the requested namespace/cluster
            #    
            mara_data = get('http://%s/v2/apps/%s' % (master, ocho_data[name]))
            code = mara_data.status_code
            assert code == 200 or code == 201, "Could not scale: Marathon couldn't find the correct app id for %s (HTTP %d)" % (name, code)
            curr = json.loads(mara_data.text)['app']

            #
            # - Scale cpu, mem, or other resources; need to kill all pods (Marathon will run a set of new resized containers)
            #
            resources = ['cpus', 'mem']

            if set(resources) & set(spec.keys()):

                down = _kill(name, None)
                assert down, 'Could not scale: The namespace/cluster %s is either invalid or empty' % name

            #
            # - Scale instance # down. Need to gracefully kill ochopods before telling Marathon to kill 
            # - the corresponding tasks.
            #
            elif 'instances' in spec and curr['instances'] > spec['instances']:

                assert spec['instances'] >= 0, "Could not scale: Invalid scaling instance number (%d) for %s" % (spec['instances'], name)
                delta = curr['instances'] - spec['instances']

                #
                # - Sort marathon task data by started time and slice off the older tasks (scale down newer instances)
                #
                victims = sorted(curr['tasks'], key=(lambda x: x['startedAt']))[spec['instances']:]
                                                                                                                                                                                        
                def _query(zk):
                    replies = fire(zk, name, 'info')                                                                                                                                    
                    return {hints['task']: index for key, (index, hints, code) in replies.items() if code == 200}                                                                       
                
                js = run(proxy, _query, timeout)
                                                                                                                                                                                        
                #
                # - get indeces of tasks to be killed                                                                                                                                   
                #
                subset = [js[victim['id']] for victim in victims]
            
                #
                # - Kill the subset of pods
                #                                                                                                                                                                       
                down = _kill(name, subset)
                assert down, 'Could not scale: The namespace/cluster %s is either invalid or empty' % name

                #
                # - Tell marathon to delete and scale each task corresponding to the dead pods
                #
                for victim in victims:
                    reply = delete('http://%s/v2/apps/%s/tasks/%s?scale=true' % (master, ocho_data[name], victim['id']))
                    assert reply.status_code == 200 or code == 201, 'Could not scale: DELETE submission failed (HTTP %d) for %s' % (code, name)                                         
                    assert _marathon_hold(name) == [], 'Marathon timed out during deployment for %s' % name

            #
            # - Send the actual scale request; if scaling up, we didn't need to touch ochopod
            # - if scaling down, Marathon still requires this request to be sent after the DELETEs above
            #
            code = _put(ocho_data[name], spec)
            assert code == 200 or code == 201, 'Could not scale: PUT submission failed (HTTP %d) for %s' % (code, name)
            assert _marathon_hold(name) == [], 'Marathon timed out during deployment for %s' % name

            #
            # - wait for all the pods to be in the 'running' mode
            #
            js = _spin(name, ['running'], spec['instances'] if 'instances' in spec else curr['instances'])
            running = sum(1 for state, _ in js if state is not 'dead')
            logger.info('Scaled: %d/%d pods are running under %s' % (running, spec['instances'], name))

        except Exception as e:

            import sys
            logger.warning('Error on line %s' % (sys.exc_info()[-1].tb_lineno))
            logger.warning(e)
