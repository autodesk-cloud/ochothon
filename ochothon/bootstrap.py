#! /usr/bin/env python
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
"""
Utility that will clone one of our templates locally. Once the repository has been setup you can edit
integration.yml to define your CI strategy. By default it is set to build and push a Docker image. The
templates can be found under https://github.com/opaugam/ochothon-template-*. If you don't specify anything
the "default" template will be used. This image is just laid out as a minimalistic ochopod container. You
can also use specific templates by specifying an identifier. For instance:

For instance:

 $ ocho init flask
 > enter a short identifier (e.g web or database): my-stuff
 > enter the docker repo/image: project/my-stuff
 template ready in ochopod-marathon-my-stuff

 """
import hashlib
import hmac
import json

from common import shell
from sys import exit


def bootstrap(args):

    try:

        assert len(args) == 1, ''
        tokens = args[0].split('@')
        assert len(tokens) == 2, ''

        #
        # - ask a few questions
        #
        space = raw_input('> enter a identifier for your space: ')
        token = raw_input('> enter your secret token (used for the CLI + git push): ')
        slack_channel = raw_input('> enter a Slack channel to send notifications to: ')
        slack_token = raw_input('> enter your Slack API token: ')

        print '\ndeploying your space...'

        cfg = json.dumps(
            {
                'space': space,
                'token': token,
                'slack': {'channel': slack_channel, 'token': slack_token}
            })

        digest = 'sha1=' + hmac.new(tokens[0], cfg, hashlib.sha1).hexdigest()
        snippet = '''curl -X POST -d '%s' -H "Content-Type:application/json" -H "X-Signature:%s" %s''' % (cfg, digest, tokens[1])
        code, out = shell(snippet)
        js = json.loads(out.decode('utf-8'))
        print(js['out'] if code is 0 else 'i/o failure (is the bootstrapper down ?)')

    except Exception as failure:

        print('internal failure <- %s' % str(failure))
        exit(1)