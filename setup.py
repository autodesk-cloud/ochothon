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
import sys
import ez_setup

ez_setup.use_setuptools()

from ochothon import __version__
from setuptools import setup, find_packages

if sys.version_info < (2, 7):
    raise NotImplementedError("python 2.7 or higher required")

setup(
    name='ochothon',
    version=__version__,
    packages=find_packages(),
    install_requires=
    [
        'jinja2>=2.7.3'
    ],
    entry_points=
    {
        'console_scripts':
            [
                'ocho = ochothon.ocho:ocho'
            ]
    },
    package_data={
        'ochothon':
            [
                'resources/*'
            ]
    },
    author='Autodesk Inc.',
    author_email='autodesk.cloud.opensource@autodesk.com',
    url='https://git.autodesk.com/cloudplatform-compute/ochopod',
    license='Apache License, Version 2.0',
    description='Ochopod/Mesos/Marathon CLI interface'
)
