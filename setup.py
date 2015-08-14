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

import os

from setuptools import setup

execfile(os.path.join('fas_client', 'release.py'))

setup(
    name=__NAME__,
    version=__VERSION__,
    description=__DESCRIPTION__,
    long_description='',
    author=__AUTHOR__,
    author_email=__EMAIL__,
    url=__URL__,
    license=__LISENCE__,
    classifiers=['Development Status :: 2 - beta',
                 'License :: OSI Approved ::  GNU Lesser General Public License '
                 'v2 or later (LGPLv2+)',
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
    install_requires=[
        'python-fedora',
        'cliff',
        'sh',
        'path.py',
        'fedmsg',
    ],

    namespace_packages=["fas_client"],
    packages=['fas_client'],
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'fas_client = fas_client.main:main'
        ],
        'fas.client': [
            'info = fas_client.infos:Info',
            'install-account = fas_client.accountsetup:Install',
            'sync-account = fas_client.accountsetup:Sync',
            'enable-account = fas_client.accountsetup:Enable',
            'disable-account = fas_client.accountsetup:Disable',
            'daemonize = fas_client.daemonize:Daemonize',
        ],
    },

    zip_safe=False,
)
