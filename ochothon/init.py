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
import fnmatch
import os
import tempfile
import shutil

from common import shell
from jinja2 import Environment, FileSystemLoader
from os import path
from sys import exit

def init(args):
    """
    """
    tmp = tempfile.mkdtemp()
    try:

        kind = args[0] if args else 'default'
        repo = 'ochothon-template-%s' % kind
        code, _ = shell('git clone https://github.com/opaugam/%s' % repo, cwd=tmp)
        assert code == 0, 'unable to find template "%s" in git' % kind

        tag = raw_input('> enter a short identifier to describe what the image does: ')
        image = raw_input('> enter the docker repo/image to push to upon a CI build: ')

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

        local = 'ochopod-marathon-%s' % tag
        shell('mkdir %s && cp -r %s/%s/* %s' % (local, tmp, repo, local))
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
