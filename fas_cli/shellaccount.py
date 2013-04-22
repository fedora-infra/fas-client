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
from fedora.client.fas2 import AccountSystem
from systemutils import update_authconfig, read_config


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

    def __init__(self, *args, **kwargs):
        self._orig_euid = os.geteuid()
        self._orig_egid = os.getegid()
        self._orig_groups = os.getgroups()

        force_refresh = kwargs.get('force_refresh')
        if force_refresh is None:
            self.force_refresh = False
        else:
            del(kwargs['force_refresh'])
            self.force_refresh = force_refresh
        super(MakeShellAccounts, self).__init__(*args, **kwargs)

    def _make_tempdir(self, force=False):
        '''Return a temporary directory'''
        if not self._temp or force:
            # Remove any existing temp directories
            if self._temp:
                rmtree(self._temp)
            self._temp = tempfile.mkdtemp('-tmp', 'fas-', config.get('global', 'temp').strip('"'))
        return self._temp
    temp = property(_make_tempdir)

    def _refresh_users(self, force=False):
        '''Return a list of users in FAS'''
        # Cached values present, return
        if not self._users or force:
            self._users = self.user_data()
        return self._users

    users = property(_refresh_users)

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

    groups = property(_refresh_groups)

    def _refresh_good_users_group_types(self, force=False):
        # Cached values present, return
        if self._good_users and self._group_types and not force:
            return

        cla_group = config.get('global', 'cla_group').strip('"')
        if cla_group not in self.groups:
            print >> sys.stderr, 'No such group: %s' % cla_group
            print >> sys.stderr, 'Aborting.'
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

    def _refresh_good_users(self, force=False):
        '''Return a list of users in who have CLA + 1 group'''
        self._refresh_good_users_group_types(force)
        return self._good_users

    good_users = property(_refresh_good_users)

    def _refresh_group_types(self, force=False):
        '''Return a list of users in group with various types'''
        self._refresh_good_users_group_types(force)
        return self._group_types

    group_types = property(_refresh_group_types)

    def filter_users(self, valid_groups=None, restricted_groups=None):
        '''Return a list of users who get normal and restricted accounts on a machine'''
        if valid_groups is None:
            valid_groups = []
        if restricted_groups is None:
            restricted_groups = []

        all_groups = valid_groups + restricted_groups

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
                        print >> sys.stderr, 'No such group type: %s' % group_type
                        continue
                    uids.update(self.group_types[group_type])
            else:
                if group not in self.groups:
                    print >> sys.stderr, 'No such group: %s' % group
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

    def passwd_text(self, users):
        '''Create the text password file'''
        i = 0
        home_dir_base = os.path.join(prefix, config.get('users', 'home').strip('"').lstrip('/'))

        # Touch shadow and secure the permissions
        shadow_file = codecs.open(os.path.join(self.temp, 'shadow.txt'), mode='w', encoding='utf-8')
        shadow_file.close()
        os.chmod(os.path.join(self.temp, 'shadow.txt'), 00600)

        passwd_file = codecs.open(os.path.join(self.temp, 'passwd.txt'), mode='w', encoding='utf-8')
        shadow_file = codecs.open(os.path.join(self.temp, 'shadow.txt'), mode='w', encoding='utf-8')

        for uid, user in sorted(users.iteritems()):
            username = self.users[uid]['username']
            human_name = self.users[uid]['human_name']
            password = self.users[uid]['password']
            home_dir = '%s/%s' % (home_dir_base, username)
            shell = user['shell']

            passwd_file.write('=%s %s:x:%s:%s:%s:%s:%s\n' % (uid, username, uid, uid, human_name, home_dir, shell))
            passwd_file.write('0%i %s:x:%s:%s:%s:%s:%s\n' % (i, username, uid, uid, human_name, home_dir, shell))
            passwd_file.write('.%s %s:x:%s:%s:%s:%s:%s\n' % (username, username, uid, uid, human_name, home_dir, shell))

            shadow_file.write('=%s %s:%s::::7:::\n' % (uid, username, password))
            shadow_file.write('0%i %s:%s::::7:::\n' % (i, username, password))
            shadow_file.write('.%s %s:%s::::7:::\n' % (username, username, password))
            i += 1

        passwd_file.close()
        shadow_file.close()

    def groups_text(self, users):
        '''Create the text groups file'''
        i = 0
        group_file = codecs.open(os.path.join(self.temp, 'group.txt'), 'w')

        # First create all of our users/groups combo
        # Only create user groups for users that actually exist on the system
        for uid in sorted(users.iterkeys()):
            username = self.users[uid]['username']
            group_file.write('=%s %s:x:%s:\n' % (uid, username, uid))
            group_file.write('0%i %s:x:%s:\n' % (i, username, uid))
            group_file.write('.%s %s:x:%s:\n' % (username, username, uid))
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
                    # This means that the user is most likely disabled.
                    pass

            members.sort()
            memberships = ','.join(members)
            group_file.write('=%i %s:x:%i:%s\n' % (gid, groupname, gid, memberships))
            group_file.write('0%i %s:x:%i:%s\n' % (i, groupname, gid, memberships))
            group_file.write('.%s %s:x:%i:%s\n' % (groupname, groupname, gid, memberships))
            i += 1

        group_file.close()

    def create_home_dirs(self, users, modes=None):
        ''' Create homedirs and home base dir if they do not exist '''
        if modes is None:
            modes = {}
        home_dir_base = to_bytes(os.path.join(prefix, config.get('users', 'home').strip('"').lstrip('/')))
        if not os.path.exists(home_dir_base):
            os.makedirs(home_dir_base, mode=0755)
            if have_selinux:
                selinux.restorecon(home_dir_base)
        for uid in users:
            username = to_bytes(self.users[uid]['username'])
            home_dir = os.path.join(home_dir_base, username)
            if not os.path.exists(home_dir):
                syslog.syslog('Creating homedir for %s' % username)
                copytree('/etc/skel/', home_dir)
                os.path.walk(home_dir, _chown, [int(uid), int(uid)])
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
        home_dir_base = os.path.join(prefix, config.get('users', 'home').strip('"').lstrip('/'))
        valid_users = [self.users[uid]['username'] for uid in users]
        current_users = os.listdir(home_dir_base)
        modes = {}
        for user in current_users:
            if user not in valid_users:
                home_dir = os.path.join(home_dir_base, user)
                dir_stat = os.stat(home_dir)
                if dir_stat.st_uid != 0:
                    modes[user] = dir_stat.st_mode
                    syslog.syslog('Locking permissions on %s' % home_dir)
                    os.chmod(home_dir, 0700)
                    os.chown(home_dir, 0, 0)
        return modes

    def create_ssh_key_user(self, uid):
        home_dir_base = os.path.join(prefix, config.get('users', 'home').strip('"').lstrip('/'))
        username = self.users[uid]['username']
        ssh_dir = to_bytes(os.path.join(home_dir_base, username, '.ssh'))
        key_file = os.path.join(ssh_dir, 'authorized_keys')
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
            f = codecs.open(key_file, mode='a+', encoding='utf-8')
            if f.read() != key + '\n':
               f.truncate(0)
               f.write(key + '\n')
            f.close()
            os.chmod(key_file, 0600)
            #os.path.walk(ssh_dir, _chown, [int(uid), int(uid)])
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
        home_dir_base = os.path.join(prefix, config.get('users', 'home').strip('"').lstrip('/'))
        for uid in users:
            pw = pwd.getpwuid(int(uid))
            lock_dir = False

            self.drop_privs(pw)

            try:
                self.create_ssh_key_user(uid)
            except IOError, e:
                print >> sys.stderr, 'Error when creating SSH key for %s!' % uid
                print >> sys.stderr, 'Locking their home directory, please investigate.'
                lock_dir = True

            self.restore_privs()

            if lock_dir:
                os.chmod(pw.pw_dir, 0700)
                os.chown(pw.pw_dir, 0, 0)

    def install_passwd_db(self):
        '''Install the password database'''
        try:
            log.debug('Installing group database into %s', filename)
            move(os.path.join(self.temp, 'passwd.db'), os.path.join(prefix, 'var/db/passwd.db'))
        except IOError, e:
            print >> sys.stderr, 'ERROR: Could not install passwd db: %s' % e

    def install_shadow_db(self):
        '''Install the shadow database'''
        try:
            log.debug('Installing group database into %s', filename)
            move(os.path.join(self.temp, 'shadow.db'), os.path.join(prefix, 'var/db/shadow.db'))
        except IOError, e:
            print >> sys.stderr, 'ERROR: Could not install shadow db: %s' % e

    def install_group_db(self):
        '''Install the group database'''
        try:
            log.debug('Installing group database into %s', filename)
            move(os.path.join(self.temp, 'group.db'), os.path.join(prefix, 'var/db/group.db'))
        except IOError, e:
            print >> sys.stderr, 'ERROR: Could not install group db: %s' % e
            log.error('Could not install group db: %s', e)

    def get_username_data(self, username):
        """ Returns a bunch() of FAS user's metadata"""
        if username:
            return self.person_by_username(username)

#    def user_info(self, username):
#        '''Print information on a user'''
#        person = self.person_by_username(username)
#        if not person:
#            print 'No such person: %s' % username
#            return
#        print 'User: %s' % person['username']
#        print ' Name: %s' % person['human_name']
#        print ' Created: %s' % person['creation'].split(' ')[0]
#        print ' Timezone: %s' % person['timezone']
#        print ' IRC Nick: %s' % person['ircnick']
#        print ' Locale: %s' % person['locale']
#        print ' Status: %s' % person['status']
#        print ' Approved Groups: '
#        if person['approved_memberships']:
#            for group in person['approved_memberships']:
#                print '   %s' % group['name']
#        else:
#            print '    None'
#        print ' Unapproved Groups: '
#        if person['unapproved_memberships']:
#            for group in person['unapproved_memberships']:
#                print '   %s' % group['name']
#        else:
#            print '    None'

    def cleanup(self):
        '''Perform any necessary cleanup tasks'''
        if self.temp:
            rmtree(self.temp)

class Install():
    """ Download FAS' accounts from registered group membership."""

    def get_parser(self, group_name):
        parser = super(type(self), self).get_parser(prog_name)
        parser.add_argument('--prefix', dest='prefix', default='/tmp/chroot/')
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
            action='store_true',
            default=False,
            help='Do not create/sync FAS groups informations.',
            )
        parser.add_argument(
            '-nP', '--no-password',
            dest='nopasswd',
            action='store_true',
            default=False,
            help='Do not create/sync FAS account password informations.',
            )
        parser.add_argument(
            '-nS', '--no-shadow',
            dest='noshadow',
            action='store_true',
            default=False,
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
        config = read_config()

        server_url = config.get('global', 'url').strip('"')
        username = config.get('gobal', 'login').strip('"')
        passwd = config.get('global', 'password').strip('"')

        sa = ShellAccount(server_url, username, passwd)
        users = sa.filter_users(valid_groups=valid_groups, restricted_groups=restricted_groups)
        # Required actions
        sa.make_group_db(users)
        sa.make_passwd_db(users)
        if not args.nogroup:
            sa.install_group_db()
        if not args.nopasswd:
            sa.install_passwd_db()
        if not args.noshadow:
            sa.install_shadow_db()
        if not args.nohome:
            try:
                modefile = open(config.get('global', 'modefile'), 'r')
                modes = pickle.load(modefile)
            except IOError:
                modes = {}
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
        if not opts.no_ssh_keys:
            sa.create_ssh_keys(users)

        if args.noauth:
            update_authconfig("USEDB=no")
        else:
            update_authconfig("USEDB=yes")

class Sync():
   """ Synchroniza remote FAS account with shell account."""

    def take_action(self, args):
        pass

class Enable():
    """Enable FAS' user shell account."""

    def take_action(self, args):
        update_authconfig("USEDB=yes")

class Disable():
    """Disable FAS' user shell account."""

    def take_action(self, args):
        update_authconfig("USEDB=no")

class InstallAliases():
    pass
#        '''Install the aliases file'''
#        move(os.path.join(self.temp, 'aliases'), os.path.join(prefix, 'etc/aliases'))
#        move(os.path.join(self.temp, 'relay_recipient_maps'), os.path.join(prefix, 'etc/postfix/relay_recipient_maps'))
#        subprocess.call(['/usr/bin/newaliases'])
#        if have_selinux:
#            selinux.restorecon('/etc/postfix/relay_recipient_maps')
#        subprocess.call(['/usr/sbin/postmap', '/etc/postfix/relay_recipient_maps'])
