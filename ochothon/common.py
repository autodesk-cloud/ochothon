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
from subprocess import Popen, PIPE


def shell(snippet, cwd=None, env=None):

    out = []
    pid = Popen(snippet, shell=True, stdout=PIPE, stderr=PIPE, cwd=cwd, env=env)
    while True:
        code = pid.poll()
        line = pid.stdout.readline()
        if not line and code is not None:
            break
        elif line:
            out += [line.rstrip('\n')]

    return pid.returncode, '\n'.join(out)