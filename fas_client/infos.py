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

import sys
import logging

from fas_client.shellaccount import ShellAccounts
from fas_client.systemutils import read_config, check_authconfig_value
from cliff.show import ShowOne


class Info(ShowOne):
    """ Show details about a person or group. """

    log = logging.getLogger(__name__)

    def __init__(self, app, app_args):
        super(Info, self).__init__(app, app_args)

    def get_parser(self, prog_name):
        parser = super(type(self), self).get_parser(prog_name)
        parser.add_argument("--username", dest="username", help="FAS user's login")
        parser.add_argument("--groupname", dest="groupname", help="FAS group")

        return parser

    def take_action(self, args):
        config = read_config()

        #server_url = config.get('global', 'url').strip('"')
        #username = config.get('global', 'login').strip('"')
        #passwd = config.get('global', 'password').strip('"')

        #if self.app_args.fas_server:
        #    server_url = self.app_args.fas_server
        #else:
        #    server_url = config.get('global', 'url').strip('"')

        fas = ShellAccounts(base_url=self.app_args.fas_server,
                            username=self.app_args.fas_login, password='admin')

        if args.username and args.groupname:
            self.log.info('Cannot request username & groups info at the same time.')
            sys.exit(0)

        if not args.username and not args.groupname:
           data = {}
           if check_authconfig_value('USEDB=yes'):
               data['Fas account'] = 'Installed (Enabled)'
           else:
               data['Fas account'] = 'Installed (Disabled)'
           data['Installed groups'] = [config.get('host', 'groups').strip('"').strip(',')]

        if args.username:
            data = fas.person_by_username(args.username)

            memberships = []
            for i in data['memberships']:
                memberships.append(i['display_name'])

            # Filter out infos we don't need
            data.pop('locale')
            data.pop('certificate_serial')
            data.pop('telephone')
            data.pop('affiliation')
            data.pop('latitude')
            data['password'] = '**********'
            data['passwordtoken'] = '**********'
            data['security_answer'] = '**********'
            data['memberships'] = memberships
            data['approved_memberships'] = None
            data['group_roles'] = None
            data['roles'] = None
            del data['old_password']
            # TODO: Add new fields regarding user's membership on current hosts
            #       where fas-client is running.

        if args.groupname:
            data = fas.group_by_name(args.groupname)

            data['approved_roles'] = None

        return (data.keys(), data.values())
