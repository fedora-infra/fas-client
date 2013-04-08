#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.  You should have
# received a copy of the GNU General Public License along with this program;
# if not, write to the Free Software Foundation, Inc., 51 Franklin Street,
# Fifth Floor, Boston, MA 02110-1301, USA. Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#


__name__ = 'fas_cli'
__version__ = "0.1"
__description__ = "CLI tool for FAS shell accounts management & synchronization"
__author__ = "Xavier Lamien"
__author_email__ = "laxathom@fedoraproject.org"
__url__ = "http://github.com/fedora-infra/fas"


from setuptools import setup, find_packages

from distutils.util import convert_path
from fnmatch import fnmatchcase
import os
import sys

try:
    f = open('README.rst', 'rt').read()
except IOError:
    f = ''

setup(
    name=__name__,
    version=__version__,
    description=__description__,
    long_description=f,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='LGPLv2+',
    classifiers=['Development Status :: 2 - beta',
                 'License :: OSI Approved ::  GNU Lesser General Public License v2 or later (LGPLv2+)',
                 'Programming Language :: Python',
                 'Programming Language :: Python :: 2',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3',
                 'Programming Language :: Python :: 3.2',
                 'Topic :: System :: development :: configuration',
                 'Environment :: Console',
                 ],

    platforms=['Any'],
    scripts=[],
    provides=[],
    install_requires=['fedora', 'cliff'],

    namespace_packages=["fas_cli"],
    packages=['fas_cli'],
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'fas_cli = fas_cli.main:main'
            ],
        'fas.cli': [
            'info = fas_cli.infos:Info',
            'install = fas_cli.shellaccount:Install',
            'enable = fas_cli.shellaccount:Enable',
            'disable = fas_cli.sheelaccount:Disable',
            ],
        },

    zip_safe=False,
    )
