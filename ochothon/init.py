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

import fnmatch
import os
import tempfile
import shutil

from common import shell
from jinja2 import Environment, FileSystemLoader
from os import path
from sys import exit

def init(args):

    tmp = tempfile.mkdtemp()
    try:

        #
        # - git clone the template repo from the opaugam org.
        #
        kind = args[0] if args else 'default'
        repo = 'ochothon-template-%s' % kind
        code, _ = shell('git clone https://github.com/opaugam/%s' % repo, cwd=tmp)
        assert code == 0, 'unable to find template "%s" in git' % kind

        #
        # - ask a few questions
        #
        tag = raw_input('> enter a short identifier (e.g web or database): ')
        image = raw_input('> enter the docker repo/image: ')

        #
        # - strip non-alpha characters from the tag
        #
        bad = ''.join(c for c in map(chr, range(256)) if not c.isalnum() and c not in ['-'])
        tag = tag.translate(None, bad)

        mappings = \
            {
                'tag': tag,
                'image': image
            }

        renderable = \
            [
                'Dockerfile',
                'README*',
                '*.py',
                '*.yml',
                '*.conf'
            ]

        #
        # - walk through the cloned repo
        # - render all templates
        #
        l = len(tmp) + 1
        env = Environment(loader=FileSystemLoader(tmp))
        for root, sub, items in os.walk(tmp):
            for item in items:
                absolute = path.join(root, item)
                if not '.git' in absolute:
                    for regex in renderable:
                        if fnmatch.fnmatch(item, regex):
                            rendered = env.get_template(absolute[l:]).render(mappings)
                            import codecs
                            with codecs.open(absolute, 'wb', 'utf-8') as f:
                                f.write(rendered)
                            break

        #
        # - copy the whole thing to where the script is invoked from
        #
        local = 'ochopod-marathon-%s' % tag
        code, _ = shell('mkdir %s && cp -r %s/%s/* %s' % (local, tmp, repo, local))
        print 'template ready in %s/' % local

    except KeyboardInterrupt:
        exit(0)

    except Exception as failure:
        print('internal failure <- %s' % str(failure))
        exit(1)

    finally:

        #
        # - cleanup the temporary directory
        #
        shutil.rmtree(tmp)
