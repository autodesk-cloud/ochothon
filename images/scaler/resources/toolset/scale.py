import json
import logging
import os
import time
import fnmatch
import pprint

from random import choice
from requests import delete, post, get, put
from io import fire, run, ZK

#: Our ochopod logger.
logger = logging.getLogger('ochopod')

def scale(scalees={}, timeout=60.0):

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
    pprint.pprint(ocho_data)
    pprint.pprint(mara_data)

    # def _scale(running, name, num):
    #     if ocho_data[name] == running['id']:
    #         running['instances'] = num
    #     return running

    for name, spec in scalees.iteritems():

        try:
            filtered = set(fnmatch.filter(ocho_data.keys(), name))
            assert len(filtered) < 2, ('Could not scale: Found multiple clusters under %s' % name)
            assert len(filtered) > 0, ('Could not scale: No cluster under %s was found' % name)
            name = filtered.pop()
            # assert ocho_data[name] in [running['id'] for running in mara_data['apps']], ('Could not scale: Ochopod reported wrong app id for %s' % name)
            # mara_data['apps'] = map(lambda running: _scale(running, name, num), mara_data['apps'])
            reply = put('http://%s/v2/apps/%s' % (master, ocho_data[name]), data=json.dumps(spec), headers=headers)
            code = reply.status_code
            assert code == 200 or code == 201, 'submission failed (HTTP %d)' % code

        except Exception as e:
            print e
            logger.warning(e)

    # for running in mara_data['apps']:

    #     try:

    #         if ocho_data[running['id']] in scalees:

    #             running['instances'] = num
    #             map(lambda x: [] if x == ocho_data[running['id']], scalees)
            

    #     except Exception as e:

    #         logger.warning(e)
    
