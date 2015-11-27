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
import ochothon

from argparse import ArgumentParser
from sys import exit


def ocho():
    """
    Top level CLI script invoking one of the supported commands.
    """

    commands = ['bootstrap', 'cli', 'init']
    parser = ArgumentParser(description='ochothon CLI %s' % ochothon.__version__)
    parser.add_argument('command', type=str, help='supported commands: %s' % ','.join(commands))
    parser.add_argument('extra', metavar='extra arguments', type=str, nargs='*', help='0+ arguments (type "help" for detailed information)')
    args = parser.parse_args()
    if args.command not in commands:
        print 'invalid command (type ocho -h for details)'
        exit(1)

    #
    # - import and run the specified command method
    #
    do = args.command
    imported = __import__('ochothon.%s' % do)
    module = getattr(imported, do)
    if args.extra == ['help']:
        print module.__doc__
    else:
        module.__getattribute__(do)(args.extra)

if __name__ == "__main__":
    ocho()
