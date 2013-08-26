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
# Red Hat Author(s): Mike McGrath <mmcgrath@redhat.com>
#                    Toshio Kuratomi <tkuratom@redhat.com>
#                    Ricky Zhou <rzhou@redhat.com>
# Current Author(s): Xavier Lamien <laxathom@fedoraproject.org>

import logging
import ConfigParser

from kitchen.text.converters import to_bytes
from fedora.client.fas2 import AccountSystem

from .systemutils import read_config, chown, drop_privs, restore_privs

import os
import pwd
import codecs
import tempfile

try:
    import selinux
    from shutil import rmtree
    from selinux import copytree, install as move
    have_selinux = (selinux.is_selinux_enabled() == 1)
except ImportError:
    from shutil import move, rmtree, copytree
    have_selinux = False


from path import path
from sh import makedb

config = read_config()
class ShellAccounts(AccountSystem):

    log = logging.getLogger(__name__)

    _orig_euid = None
    _orig_egid = None
    _orig_groups = None
    _users = None
    _groups = None
    _good_users = None
    _group_types = None
    _temp = None
    _tempdir = None
    _prefix = None
    dbdir = None

    def __init__(self, *args, **kwargs):
        self._orig_euid = os.geteuid()
        self._orig_egid = os.getegid()
        self._orig_groups = os.getgroups()
        self.dbdir = '/var/db/'

        force_refresh = kwargs.get('force_refresh')
        if force_refresh is None:
            self.force_refresh = False
        else:
            del(kwargs['force_refresh'])
            self.force_refresh = force_refresh
        super(ShellAccounts, self).__init__(*args, **kwargs)

    @property
    def _make_tempdir(self, force=False):
        '''Return a temporary directory'''
        if not self._temp or force:
            # Remove any existing temp directories
            if self._temp:
                rmtree(self._temp)
            if not path(self._tempdir).access(os.F_OK):
                os.makedirs(self._tempdir)
            self._temp = tempfile.mkdtemp('-tmp', 'fas-', self._tempdir)
        return self._temp

    @property
    def _refresh_users(self, force=False):
        '''Return a list of users in FAS'''
        # Cached values present, return
        if not self._users or force:
            self._users = self.user_data()
        return self._users


    @property
    def _refresh_groups(self, force=False):
        '''Return a list of groups in FAS'''
        # Cached values present, return
        if not self._groups or force:
            group_data = self.group_data(force_refresh=self.force_refresh)
            # The JSON output from FAS encodes dictionary keys as strings, but leaves
            # array elements as integers (in the case of group member UIDs).  This
            # normalizes them to all strings.
            for group in group_data:
                for role_type in ('administrators', 'sponsors', 'users'):
                    group_data[group][role_type] = [str(uid) for uid in group_data[group][role_type]]
            self._groups = group_data
        return self._groups


    def _refresh_good_users_group_types(self, force=False):
        # Cached values present, return
        if self._good_users and self._group_types and not force:
            return

        config = read_config()
        cla_group = config.get('global', 'cla_group').strip('"')
        if cla_group not in self.groups:
            self.log.info('No such group: %s\n Aborting!' % cla_group)
            sys.exit(1)

        cla_uids = self.groups[cla_group]['users'] + \
            self.groups[cla_group]['sponsors'] + \
            self.groups[cla_group]['administrators']

        user_groupcount = {}
        group_types = {}
        for uid in cla_uids:
            user_groupcount[uid] = 0

        for group in self.groups:
            group_type = self.groups[group]['type']
            if group.startswith('cla_'):
                continue
            for uid in self.groups[group]['users'] + \
                self.groups[group]['sponsors'] + \
                self.groups[group]['administrators']:
                if group_type not in group_types:
                    group_types[group_type] = set()
                group_types[group_type].add(uid)
                if uid in user_groupcount:
                    user_groupcount[uid] += 1

        good_users = set()
        for uid in user_groupcount:
            # If the user is active, has signed a CLA, and is in at least one
            # other group, add them to good_users.
            if uid in self.users and user_groupcount[uid] > 0:
                good_users.add(uid)

        self._good_users = good_users
        self._group_types = group_types

    @property
    def _refresh_good_users(self, force=False):
        '''Return a list of users in who have CLA + 1 group'''
        self._refresh_good_users_group_types(force)
        return self._good_users


    @property
    def _refresh_group_types(self, force=False):
        '''Return a list of users in group with various types'''
        self._refresh_good_users_group_types(force)
        return self._group_types


    def filter_users(self, valid_groups=None, restricted_groups=None):
        '''Return a list of users who get normal and restricted accounts on a machine'''

        if valid_groups is None:
            valid_groups = []
        if restricted_groups is None:
            restricted_groups = []

        all_groups = valid_groups + restricted_groups
        all_groups = filter(None, all_groups)

        users = {}

        for group in all_groups:
            uids = set()
            restricted = group not in valid_groups

            if group.startswith('@'):
                # Filter by group type
                group_type = group[1:]
                if group_type == 'all':
                    # It's all good as long as a the user is in CLA + one group
                    uids.update(self.good_users)
                else:
                    if group_type not in self.group_types:
                        self.log.error('No such group type: %s' % group_type)
                        continue
                    uids.update(self.group_types[group_type])
            else:
                if group not in self.groups:
                    self.log.warn('No such group: %s' % group)
                    continue
                uids.update(self.groups[group]['users'])
                uids.update(self.groups[group]['sponsors'])
                uids.update(self.groups[group]['administrators'])

            for uid in uids:
                if uid not in self.users:
                    # The user is most likely inactive.
                    continue
                if restricted:
                    # Make sure that the most privileged group wins.
                    if uid not in users:
                        users[uid] = {}
                        users[uid]['shell'] = config.get('users', 'shell').strip('"')
                        users[uid]['ssh_cmd'] = config.get('users', 'ssh_restricted_app').strip('"')
                        users[uid]['ssh_options'] = config.get('users', 'ssh_key_options').strip('"')
                else:
                    users[uid] = {}
                    users[uid]['shell'] = config.get('users', 'ssh_restricted_shell').strip('"')
                    try:
                        users[uid]['ssh_cmd'] = config.get('users', 'ssh_admin_app').strip('"')
                    except ConfigParser.NoOptionError:
                        users[uid]['ssh_cmd'] = ''
                    try:
                        users[uid]['ssh_options'] = config.get('users', 'ssh_admin_options').strip('"')
                    except ConfigParser.NoOptionError:
                        users[uid]['ssh_options'] = ''
        return users

    def create_passwd_text(self, users, passwdfile, shadowfile):
        '''Create the NSS password file'''

        home_dir_base = path(self._prefix + config.get('users', 'home').strip('"').lstrip('/'))

        #shadow_file = path(self.temp + '/shadow.txt')
        shadowfile.open(mode='w')
        shadowfile.chmod(00600)

        #passwdfile = path(self.temp + '/passwd.txt')
        passwdfile.open(mode='w')

        i = 0
        for uid, user in sorted(users.iteritems()):
            # Struct user account's metadata
            username = self.users[uid]['username']
            human_name = self.users[uid]['human_name']
            password = self.users[uid]['password']
            home_dir = '%s/%s' % (home_dir_base, username)
            shell = user['shell']

            passwdfile.write_text('=%s %s:x:%s:%s:%s:%s:%s\n' 
                                % (uid, username, uid, uid, human_name,
                                   home_dir, shell), append=True)
            passwdfile.write_text('0%i %s:x:%s:%s:%s:%s:%s\n' 
                                % (i, username, uid, uid, human_name,
                                   home_dir, shell), append=True)
            passwdfile.write_text('.%s %s:x:%s:%s:%s:%s:%s\n' 
                                % (username, username, uid, uid,
                                   human_name, home_dir, shell), append=True)

            shadowfile.write_text('=%s %s:%s::::7:::\n' 
                                % (uid, username, password), append=True)
            shadowfile.write_text('0%i %s:%s::::7:::\n' 
                                % (i, username, password), append=True)
            shadowfile.write_text('.%s %s:%s::::7:::\n' 
                                % (username, username, password), append=True)
            i += 1


    def create_home_dirs(self, users, modes=None):
        ''' Create homedirs and home base dir if they do not exist '''
        if modes is None:
            modes = {}
        home_dir_base = to_bytes(path(self._prefix + config.get('users', 'home').strip('"').lstrip('/')))
        if not os.path.exists(home_dir_base):
            os.makedirs(home_dir_base, mode=0755)
            if have_selinux:
                selinux.restorecon(home_dir_base)
        for uid in users:
            username = to_bytes(self.users[uid]['username'])
            home_dir = os.path.join(home_dir_base, username)
            if not os.path.exists(home_dir):
                self.log.info('Creating homedir for %s' % username)
                copytree('/etc/skel/', home_dir)
                os.path.walk(home_dir, chown, [int(uid), int(uid)])
            else:
                dir_stat = os.stat(home_dir)
                if dir_stat.st_uid == 0:
                    if username in modes:
                        os.chmod(home_dir, modes[username])
                    else:
                        os.chmod(home_dir, 0755)
                    os.chown(home_dir, int(uid), int(uid))

    def remove_stale_homedirs(self, users):
        ''' Remove homedirs of users that no longer have access '''
        home_dir_base = path(self._prefix + config.get('users', 'home').strip('"').lstrip('/'))
        valid_users = [self.users[uid]['username'] for uid in users]
        current_users = os.listdir(home_dir_base)
        modes = {}
        for user in current_users:
            if user not in valid_users:
                home_dir = path(home_dir_base + user)
                dir_stat = os.stat(home_dir)
                if dir_stat.st_uid != 0:
                    modes[user] = dir_stat.st_mode
                    self.log.info('Locking permissions on %s' % home_dir)
                    home_dir.chmod(0700)
                    home_dir.chown(0, 0)
        return modes

    def create_ssh_key_user(self, uid, users):
        home_dir_base = path(self._prefix + config.get('users', 'home')
                                                    .strip('"').lstrip('/'))

        username = self.users[uid]['username']
        self.log.debug('Building ssh key for user %s' % username)

        ssh_dir = path(home_dir_base + '/' + username + '/.ssh')
        key_file = path(ssh_dir + '/authorized_keys')

        if self.users[uid]['ssh_key']:
            if users[uid]['ssh_cmd'] or users[uid]['ssh_options']:
               key = []
               for key_tmp in self.users[uid]['ssh_key'].split("\n"):
                   if key_tmp:
                       key.append('command="%s",%s %s' % (users[uid]['ssh_cmd'], users[uid]['ssh_options'], key_tmp))
               key = "\n".join(key)
            else:
               key = self.users[uid]['ssh_key']
            if not os.path.exists(ssh_dir):
                os.makedirs(ssh_dir, mode=0700)
            key_file.open('a+')
            if key_file.text(encoding='utf-8') != key + '\n':
               #f.truncate(0)
               key_file.write_text(key + '\n')
            os.chmod(key_file, 0600)
            if have_selinux:
                selinux.restorecon(ssh_dir, recursive=True)
        else:
            # If the user does not have an SSH key listed, ensure
            # that their authorized_key file does not exist.
            try:
                os.remove(key_file)
            except OSError:
                pass

    def create_ssh_keys(self, users):
        """ Create SSH keys from given FAS's account"""
        home_dir_base = path(self._prefix + config.get('users', 'home').strip('"').lstrip('/'))
        for uid in users:
            pw = pwd.getpwuid(int(uid))
            lock_dir = False

            drop_privs(pw)

            try:
                self.create_ssh_key_user(uid, users)
            except IOError, e:
                self.log.error('Error when creating SSH key for %s!' % uid)
                self.log.error('Locking their home directory, please investigate.')
                lock_dir = True

            # Restore priveleges
            os.seteuid(self._orig_euid)
            os.setegid(self._orig_egid)
            os.setgroups(self._orig_groups)

            if lock_dir:
                os.chmod(pw.pw_dir, 0700)
                os.chown(pw.pw_dir, 0, 0)

    def install_passwd_db(self):
        '''Install the password database'''
        try:
            self.log.debug('Installing group database into %s', self.temp)
            move(path(self.temp + '/passwd.db'), path(self._prefix + '/var/db/passwd.db'))
        except IOError, e:
            self.log.error('Could not install passwd db: %s' % e)

    def install_shadow_db(self):
        '''Install the shadow database'''
        try:
            self.log.debug('Installing group database into %s', self.temp)
            move(os.path.join(self.temp, 'shadow.db'), os.path.join(self._prefix, 'var/db/shadow.db'))
        except IOError, e:
            self.log.error('Could not install shadow db: %s' % e)

    def install_group_db(self):
        '''Install the group database'''
        try:
            self.log.debug('Installing group database into %s', self.temp)
            move(os.path.join(self.temp, 'group.db'), os.path.join(self._prefix, 'var/db/group.db'))
        except IOError, e:
            self.log.error('Could not install group db: %s' % e)

    def make_db(self, input, output=None):
        """ Compile input file to NSS db"""

        makedb(input, output=output)

    def make_group_db(self, users, filename, install=True):
        '''Compile the groups file'''
        input_file = path(self.temp).joinpath(filename + '.txt')
        output_file = path(self.temp).joinpath(filename + '.db')

        self.create_groups_text(users, input_file )
        self.make_db(input_file, output_file)

        if install:
            output_file.move(self.dbdir)

    def make_passwd_db(self, users, passwd, shadow,
                       install_passwd=True, install_shadow=True):
        '''Compile the password and shadow files'''
        passwd_input = path(self.temp).joinpath(passwd + '.txt')
        passwd_output = path(self.temp).joinpath(passwd + '.db')
        shadow_input = path(self.temp).joinpath(shadow + '.txt')
        shadow_output = path(self.temp).joinpath(shadow + '.db')

        self.create_passwd_text(users, passwd_input, shadow_input)

        self.make_db(passwd_input, passwd_output)
        self.make_db(shadow_input, shadow_output)

        shadow_input.chmod(0400)
        shadow_output.chmod(0400)

        if install_passwd:
            passwd_output.move(self.dbdir)
        if install_shadow:
            shadow_output.move(self.dbdir)

    def create_groups_text(self, users, groupfile):
        '''Create the NSS groups file'''
        groupfile.open('w')

        # First create all of our users/groups combo, then
        # Only create user groups for users that actually exist on the system
        i = 0
        for uid in sorted(users.iterkeys()):
            username = self.users[uid]['username']
            groupfile.write_text('=%s %s:x:%s:\n' %
                                 (uid, username, uid), append=True)
            groupfile.write_text('0%i %s:x:%s:\n' %
                                 (i, username, uid), append=True)
            groupfile.write_text('.%s %s:x:%s:\n' %
                                 (username, username, uid), append=True)
            i += 1

        for groupname, group in sorted(self.groups.iteritems()):
            gid = group['id']
            members = []
            memberships = ''

            for member_uid in group['administrators'] + \
                group['sponsors'] + \
                group['users']:
                try:
                    members.append(self.users[member_uid]['username'])
                except KeyError:
                    # This means that the user is most likely disabled :/
                    pass

            members.sort()
            memberships = ','.join(members)
            groupfile.write_text('=%i %s:x:%i:%s\n' 
                                % (gid, groupname, gid, memberships), append=True)
            groupfile.write_text('0%i %s:x:%i:%s\n' 
                                % (i, groupname, gid, memberships), append=True)
            groupfile.write_text('.%s %s:x:%i:%s\n' 
                                % (groupname, groupname, gid, memberships),
                                                              append=True)
            i += 1


    def get_username_data(self, username):
        """ Returns a bunch() of FAS user's metadata """
        if username:
            return self.person_by_username(username)

    def cleanup(self):
        """ Perform any necessary cleanup tasks """
        if self.temp:
            rmtree(self.temp)

    temp = _make_tempdir
    users = _refresh_users
    groups = _refresh_groups
    good_users = _refresh_good_users
    group_types = _refresh_group_types
