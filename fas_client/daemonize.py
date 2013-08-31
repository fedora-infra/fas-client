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
import sys, signal, time
from cliff.command import Command

from .systemutils import read_config, enable_authconfig, disable_authconfig
from .shellaccount import ShellAccounts

import fedmsg

config = read_config()
class Daemonize(Command):
    """ Run fas-client as a daemon. """

    log = logging.getLogger(__name__)

    def sig_handler(self, signum = None, frame = None):
        self.log.info('\nCaught signal %s from signals handler' % signum)

        time.sleep(1)  #here check if process is done
        sys.exit(0)


    def take_action(self, args):
        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
            signal.signal(sig, self.sig_handler)

        import re
        configs = fedmsg.config.load_config([], None)

        configs['mute'] = True
        configs['timeout'] = 0

        group_update = 'group.member.sponsor'
        user_update = 'user.update'
        user_data = ['ssh_key', 'password', 'ircnick']

        for name, endpoint, topic, sig in fedmsg.tail_messages(**configs):
            fas_group_topic = re.compile(group_update)
            fas_user_topic = re.compile('fas.user.update')

            if fas_group_topic.search(topic):
                self.log.debug('Receiving group update notification.')
                if sig['msg']['group'] in config.get('host', 'groups').split('"').split(','):
                    self.log.debug('Received an update from installed groups')
                    #update_shell_account()

            if fas_user_topic.search(topic):
                self.log.debug('Receiving user update notification.')
                for i in sig['msg']['fields']:
                    if i in user_data:
                        self.log.debug('Received an update from installed account')
                        #update_shell_account()
