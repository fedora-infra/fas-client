#!/usr/bin/python
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
# Author(s): Xavier Lamien <laxathom@fedoraproject.org>

import logging
import sys
import codecs
import locale

import cliff.app
import cliff.commandmanager
from cliff.commandmanager import CommandManager

import fas_cli.systemutils

__version__ = 2.0
__description__ = "CLI tool for FAS shell accounts management & synchronization"

class FasClient(cliff.app.App):

    log = logging.getLogger(__name__)

    def __init__(self):
        manager = cliff.commandmanager.CommandManager('fas.cli')
        super(FasClient, self).__init__(
            description=__description__,
            version=__version__,
            command_manager=manager,
            stdout=codecs.getwriter(locale.getpreferredencoding())(sys.stdout),
            stderr=codecs.getwriter(locale.getpreferredencoding())(sys.stderr),
        )

    def build_option_parser(self, description, version):
        """Common optional options"""
        config = read_config()
        parser = super(FasClient, self).build_option_parser(description, version)
        parser.add_argument(
            '--fas-server',
            dest='fas_server',
            default=config.get('global', 'url').strip('"'),
            help='URL of FAS server.',
            )
        parser.add_argument(
            '--fas-login',
            dest='fas_login',
            default=config.get('global', 'login').strip('"'),
            help='Login to authenticate against FAS server.',
            )

        return parser

    def initialize_app(self, argv):
        self.log.debug('initialize_app')

    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.log.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.log.debug('got an error: %s', err)

    # Overload run_subcommand to gracefully handle unknown commands.
    def run_subcommand(self, argv):
        try:
            self.command_manager.find_command(argv)
        except ValueError as e:
            if "Unknown command" in str(e):
                print "%r is an unknown command" % ' '.join(argv)
                print "Try \"fas_cli -h\""
                sys.exit(1)
            else:
                raise

        return super(FasClient, self).run_subcommand(argv)


def main(argv=sys.argv[1:]):
    myapp = FasClient()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
