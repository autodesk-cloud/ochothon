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
import imp
import logging
import sys

from argparse import ArgumentParser
from os import listdir
from os.path import dirname, isfile, join
from ochopod.core.fsm import diagnostic
from toolset.tool import Template

#: Our ochopod logger.
logger = logging.getLogger('ochopod')


def go():
    """
    Entry point for the portal tool-set. This script will look for python modules in the /commands sub-directory. This
    is what is invoked from within the portal's flask endpoint (e.g when the user types something in the cli)
    """

    #
    # - start by simplifying a bit the console logger to look more CLI-ish
    #
    for handler in logger.handlers:
        handler.setFormatter(logging.Formatter('%(message)s'))

    try:

        def _import(where, funcs):
            try:
                for script in [f for f in listdir(where) if isfile(join(where, f)) and f.endswith('.py')]:
                    try:
                        module = imp.load_source(script[:-3], join(where, script))
                        if hasattr(module, 'go') and callable(module.go):
                            tool = module.go()
                            assert isinstance(tool, Template), 'boo'
                            assert tool.tag, ''
                            funcs[tool.tag] = tool

                    except Exception as failure:

                        logger.warning('failed to import %s (%s)' % (script, diagnostic(failure)))

            except OSError:
                pass

        #
        # - disable .pyc generation
        # - scan for tools to import
        # - each .py module must have a go() callable as well as a COMMAND attribute
        # - the COMMAND attribute tells us what the command-line invocation looks like
        #
        tools = {}
        sys.dont_write_bytecode = True
        _import('%s/commands' % dirname(__file__), tools)

        def _usage():
            return 'available commands -> %s' % ', '.join(sorted(tools.keys()))

        parser = ArgumentParser(description='', prefix_chars='+', usage=_usage())
        parser.add_argument('command', type=str, help='command (e.g ls for instance)')
        parser.add_argument('extra', metavar='extra arguments', type=str, nargs='*', help='zero or more arguments')
        args = parser.parse_args()
        total = [args.command] + args.extra
        if args.command == 'help':
            logger.info(_usage())
            exit(0)

        def _sub(sub):
            for i in range(len(total)-len(sub)+1):
                if sub == total[i:i+len(sub)]:
                    return 1
            return 0

        matched = [tool for tool in tools.keys() if _sub(tool.split(' '))]
        if not matched:

            logger.info('unknown command (%s)' % _usage())

        else:

            #
            # - simply invoke the tool
            # - remove the command tokens first and pass the rest as arguments
            # - each tool will parse its own commandline
            #
            picked = matched[0]
            tokens = len(picked.split(' ')) - 1
            exit(tools[picked].run(args.extra[tokens:]))

    except AssertionError as failure:

        logger.error('shutting down <- %s' % failure)

    except Exception as failure:

        logger.error('shutting down <- %s' % diagnostic(failure))

    exit(1)