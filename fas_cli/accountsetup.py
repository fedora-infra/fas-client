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
from cliff.command import Command

from .systemutils import read_config, enable_authconfig, disable_authconfig
from .shellaccount import ShellAccounts

config = read_config()

class Install(Command):
    """ Download & create FAS' accounts from registered group membership."""

    log = logging.getLogger(__name__)

    def __init__(self, app, app_args):
        super(Install, self).__init__(app, app_args)

    def get_parser(self, prog_name):
        parser = super(type(self), self).get_parser(prog_name)
        parser.add_argument('--prefix', dest='prefix', default='/')
        parser.add_argument(
            '--disable-auth',
            dest='noauth',
            action='store_true',
            default=False,
            help='Disable local (shell) authentication of FAS account',
            )
        parser.add_argument(
            '-nH', '--no-home',
            dest='nohome',
            action='store_true',
            default=False,
            help='Do not create local (shell) home directory of FAS user.',
            )
        parser.add_argument(
            '-nG', '--no-group', 
            dest='nogroup',
            action='store_false',
            default=True,
            help='Do not create/sync FAS groups informations.',
            )
        parser.add_argument(
            '-nP', '--no-password',
            dest='nopasswd',
            action='store_false',
            default=True,
            help='Do not create/sync FAS account password informations.',
            )
        parser.add_argument(
            '-nS', '--no-shadow',
            dest='noshadow',
            action='store_false',
            default=True,
            help='Do not create/sync FAS account shadow informations.',
            )
        parser.add_argument(
            '-ns', '--no-ssh',
            dest='nossh',
            action='store_true',
            default=False,
            help='Do not create SSH keys.',
            )
        parser.add_argument(
            '--force-refresh',
            dest='refresh',
            action='store_true',
            default=False,
            help='Always use metadata from FAS server, skipping local cache.',
            )
        parser.add_argument(
            '-NS', '--no-session',
            dest='nosession',
            action='store_true',
            default=False,
            help='Do not use session management from FAS.',
            )

        return parser

    def take_action(self, args):

        passwd = config.get('global', 'password').strip('"')
        temp = config.get('global', 'temp').strip('"')

        groups = []
        restricted_groups = []
        groups = config.get('host','groups').strip('"').split(',')
        restricted_groups = config.get('host', 'restricted_groups').strip('"').split(',')

        sa = ShellAccounts(prefix=args.prefix, tempdir=temp,
                           base_url=self.app_args.fas_server,
                           username=self.app_args.fas_login, password=passwd)
        users = sa.filter_users(valid_groups=groups,
                                restricted_groups=restricted_groups)

        # Required actions
        sa.make_group_db(users, 'group', args.nogroup)
        sa.make_passwd_db(users, 'passwd', 'shadow', args.nopasswd, args.noshadow)


        if not args.nohome:
            try:
                modefile = open(config.get('global', 'modefile'), 'r')
                modes = pickle.load(modefile)
            except IOError, e:
                modes = {}
                self.log.debug('Unable to read from file: %s' % e)
            else:
                modefile.close()
            sa.create_home_dirs(users, modes=modes)
            new_modes = sa.remove_stale_homedirs(users)
            modes.update(new_modes)
            try:
                modefile = open(config.get('global', 'modefile'), 'w')
                pickle.dump(modes, modefile)
            except IOError:
                pass
            else:
                modefile.close()

        if args.noauth:
            disable_authconfig()
        else:
            enable_authconfig()

        if not args.nossh:
            sa.create_ssh_keys(users)


class Sync(Command):
    """ Synchroniza remote FAS account with shell account."""

    log = logging.getLogger(__name__)

    def take_action(self, args):
        pass

class Enable(Command):
    """Enable FAS' user shell account."""

    log = logging.getLogger(__name__)

    def take_action(self, args):
        self.log.debug('Updating authconfig')
        if enable_authconfig() == 0:
            self.log.info("FAS accounts enabled.")


class Disable(Command):
    """Disable FAS' user shell account."""

    log = logging.getLogger(__name__)

    def take_action(self, args):
        self.log.debug('Updating authconfig')
        if disable_authconfig() == 0:
            self.log.info("FAS accounts disabled.")

class InstallAliases(Command):
    pass
#        '''Install the aliases file'''
#        move(os.path.join(self.temp, 'aliases'), os.path.join(prefix, 'etc/aliases'))
#        move(os.path.join(self.temp, 'relay_recipient_maps'), os.path.join(prefix, 'etc/postfix/relay_recipient_maps'))
#        subprocess.call(['/usr/bin/newaliases'])
#        if have_selinux:
#            selinux.restorecon('/etc/postfix/relay_recipient_maps')
#        subprocess.call(['/usr/sbin/postmap', '/etc/postfix/relay_recipient_maps'])
