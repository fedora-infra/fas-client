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
import grp
import logging

from cliff.show import ShowOne
from munch import Munch

from fas_client.shellaccount import ShellAccounts
from fas_client.systemutils import read_config, check_authconfig_value
from fedora.client.fas2 import AccountStatus, GroupStatus


class Info(ShowOne):
    """
    Show details about a person or group based on local system configuration.
    """

    log = logging.getLogger(__name__)

    def __init__(self, app, app_args):
        super(Info, self).__init__(app, app_args)

    def get_parser(self, prog_name):
        parser = super(type(self), self).get_parser(prog_name)
        parser.add_argument("--username", dest="username", help="FAS login")
        parser.add_argument("--groupname", dest="groupname", help="FAS group name")

        return parser

    def take_action(self, args):
        config = read_config(self.app_args.configfile)

        fas = ShellAccounts(base_url=self.app_args.fas_server,
                            token_api=config.get('global', 'tokenapi'))

        if args.username and args.groupname:
            self.log.info(
                'Cannot request username & groups info at the same time.')
            sys.exit(0)

        data = Munch()
        configured_group = config.get('host', 'groups').strip('"').split(',')

        if not args.username and not args.groupname:
            if check_authconfig_value('USEDB=yes'):
                data['Fas account'] = 'Enabled'
            else:
                data['Fas account'] = 'Disabled'

            data['synchronized groups'] = [
                g.gr_name for g in grp.getgrall() if g.gr_name in configured_group
            ]

            data['Un-synchronized group'] = []
            for g in configured_group:
                try:
                    grp.getgrnam(g)
                except KeyError:
                    data['Un-synchronized group'].append(g)

        if args.username:
            person = fas.get_person_by_username(args.username)

            memberships = []
            for i in person.membership:
                memberships.append(i.group_name)

            data['username'] = person.username
            data['fullname'] = person.fullname
            data['status'] = AccountStatus(person.status).name
            data['memberships'] = memberships
            # TODO: Add new fields regarding user's membership on current hosts
            # TODO: where fas-client is running.

        if args.groupname:
            group = fas.get_group_by_name(args.groupname)

            data['name'] = group.name
            data['FAS status'] = GroupStatus(group.status).name
            data['members'] = '{} members'.format(len(group.members))

            if group.name in configured_group:
                try:
                    grp.getgrnam(group.name)
                    data['synchronized'] = 'Yes'
                except KeyError:
                    data['synchronized'] = 'No'
            else:
                data['info'] = 'This group has not been setup for this host.'

        return data.keys(), data.values()
