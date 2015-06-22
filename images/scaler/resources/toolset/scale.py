import json
import logging
import os
import fnmatch

from ochopod.core.utils import retry
from random import choice
from requests import get, put
from io import fire, run, ZK

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def scale(scalees={}, timeout=60.0):
    """
        Tool for scaling a set of scalee apps running under Ochopod and Marathon using a dict of specifications.
        E.g., you may use:
        scalees = {
            '<namespace>.<cluster>': {
                'instances': 5,
                'mem': 32.0
            }
        }
        Scaling parameters include: 'instances', 'mem', 'cpu'.

        :param scalees: a dict mapping a cluster/namespace key to a secondary dict of specifications, according to which
        the corresponding app will be scaled.
        :param timeout: float amount of seconds allowed for scaling each namespace/cluster in scalees.    
    """

    #
    # - we need to pass the framework master IPs around (ugly)
    #
    assert 'MARATHON_MASTER' in os.environ, '$MARATHON_MASTER not specified... check scaler pod'
    master = choice(os.environ['MARATHON_MASTER'].split(','))
    headers = \
        {
            'content-type': 'application/json',
            'accept': 'application/json'
        }

    def _query(zk):
        replies = fire(zk, '*', 'info')
        return len(replies), dict((key.rstrip(' .#%s' % index), hints['application']) for key, (index, hints, code) in replies.items() if code == 200)

    proxy = ZK.start([node for node in os.environ['OCHOPOD_ZK'].split(',')])

    _, ocho_data = run(proxy, _query, timeout)
    
    mara_data = json.loads(get('http://%s/v2/apps' % master).text)

    for name, spec in scalees.iteritems():

        try:

            filtered = set(fnmatch.filter(ocho_data.keys(), name))
            assert len(filtered) < 2, ('Could not scale: Found multiple clusters under %s' % name)
            assert len(filtered) > 0, ('Could not scale: No namespace/cluster found under %s ' % name)
            name = filtered.pop()
            reply = put('http://%s/v2/apps/%s' % (master, ocho_data[name]), data=json.dumps(spec), headers=headers)
            code = reply.status_code
            assert code == 200 or code == 201, 'submission failed (HTTP %d)' % code

            #
            # - wait for all the pods to be in the 'running' mode
            # - the 'application' hint is set by design to the marathon application identifier
            # - the sequence counters allocated to our new pods are returned as well
            #
            target = ['dead', 'running']
            @retry(timeout=timeout, pause=3, default={})
            def _spin():
                def _query(zk):
                    replies = fire(zk, name, 'info')
                    return [(hints['process'], seq) for seq, hints, _ in replies.values()
                            if hints['application'] == application and hints['process'] in target]

                js = run(proxy, _query)
                assert len(js) == spec['instances'], 'not all pods running yet'
                return js

            js = _spin()
            running = sum(1 for state, _ in js if state is not 'dead')
            up = [seq for _, seq in js]
            ok = spec['instances'] == running
            logger.debug('Scaled: %d/%d pods are running for %s' % (running, spec['instances'], name))

        except Exception as e:

            print e
            logger.warning(e)
    
