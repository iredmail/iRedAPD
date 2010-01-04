#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <michaelbibby (at) gmail.com>

import os, os.path
import sys
import ConfigParser
import socket
import asyncore, asynchat
import logging
import ldap
import daemon

__version__ = "1.0"

ACTION_ACCEPT = "action=DUNNO"
ACTION_DEFER = "action=DEFER_IF_PERMIT Service temporarily unavailable"
ACTION_REJECT = 'action=REJECT Not Authorized'
ACTION_DEFAULT = ACTION_ACCEPT

# Get config file.
if len(sys.argv) != 2:
    sys.exit('Usage: %s /path/to/iredapd.ini')
else:
    config_file = sys.argv[1]

    # Check file exists.
    if not os.path.exists(config_file):
        sys.exit('File not exist: %s.' % config_file)

# Read configurations.
cfg = ConfigParser.SafeConfigParser()
cfg.read(config_file)

class apdChannel(asynchat.async_chat):
    def __init__(self, conn, remoteaddr):
        asynchat.async_chat.__init__(self, conn)
        self.buffer = []
        self.map = {}
        self.set_terminator('\n')
        logging.debug("Connect from " + remoteaddr[0])

    def push(self, msg):
        asynchat.async_chat.push(self, msg + '\n')

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        if len(self.buffer) is not 0:
            line = self.buffer.pop()
            logging.debug("smtp session: " + line)
            if line.find('=') != -1:
                key = line.split('=')[0]
                value = line.split('=')[1]
                self.map[key] = value
        elif len(self.map) != 0:
            try:
                modeler = LDAPModeler()
                result = modeler.handle_data(self.map)
                logging.debug("result replying: %s." % str(result))
                if result != None:
                    action = result
                else:
                    action = ACTION_ACCEPT
            except Exception, e:
                action = ACTION_DEFAULT
                logging.debug('Error: %s. Use default action instead: %s' % (str(e), str(action)) )
            logging.info('%s -> %s, %s' % (self.map['sender'], self.map['recipient'], str(action).split('=')[1] ))
            self.push(action)
            self.push('')
            asynchat.async_chat.handle_close(self)
            #logging.debug("Connection closed")
        else:
            action = ACTION_DEFER
            logging.debug("replying: " + action)
            self.push(action)
            self.push('')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")

class apdSocket(asyncore.dispatcher):
    def __init__(self, localaddr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(localaddr)
        self.listen(5)
        ip, port = localaddr
        logging.info("Starting iredapd (v%s, pid: %d), listening on %s:%s." % (__version__, os.getpid(), ip, str(port)))


    def handle_accept(self):
        conn, remoteaddr = self.accept()
        channel = apdChannel(conn, remoteaddr)

class LDAPModeler:
    def __init__(self):
        # Read LDAP server settings.
        self.uri = cfg.get('ldap', 'uri', 'ldap://127.0.0.1:389')
        self.binddn = cfg.get('ldap', 'binddn')
        self.bindpw = cfg.get('ldap', 'bindpw')
        self.baseDN = cfg.get('ldap', 'basedn')

        # Initialize ldap connection.
        try:
            self.conn = ldap.initialize(self.uri)
            logging.debug('LDAP connection initialied success.')
        except Exception, e:
            logging.error('LDAP initialized failed: %s.' % str(e))
            sys.exit()

        # Bind to ldap server.
        if self.binddn != '' and self.bindpw != '':
            try:
                self.conn.bind_s(self.binddn, self.bindpw)
                logging.debug('LDAP bind success.')
            except ldap.INVALID_CREDENTIALS:
                logging.error('LDAP bind failed, incorrect bind dn or password.')
                sys.exit()
            except Exception, e:
                logging.error('LDAP bind failed: %s.' % str(e))
                sys.exit()

    def __get_access_policy(self, listname):
        """Get access policy of mail list.

        return (dn_of_mail_list, value_of_access_policy,)"""

        logging.debug('__get_access_policy (list): %s' % listname)

        # Search mail list object.
        searchBasedn = 'mail=%s,ou=Groups,domainName=%s,%s' % (listname, listname.split('@')[1], self.baseDN)
        searchScope = ldap.SCOPE_BASE
        searchFilter = '(&(objectClass=mailList)(accountStatus=active)(enabledService=mail)(enabledService=deliver)(mail=%s))' % listname

        logging.debug('__get_access_policy (searchBasedn): %s' % searchBasedn)
        logging.debug('__get_access_policy (searchScope): %s' % searchScope)
        logging.debug('__get_access_policy (searchFilter): %s' % searchFilter)

        try:
            result = self.conn.search_s(searchBasedn, searchScope, searchFilter, ['accessPolicy'])
            logging.debug('__get_access_policy (search result): %s' % str(result))
        except ldap.NO_SUCH_OBJECT:
            logging.debug('__get_access_policy (not a mail list: %s) Returned (None)' % listname)
            return (None, None)
        except Exception, e:
            logging.debug('__get_access_policy (ERROR while searching list): %s' % str(e))
            return (None, None)

        if len(result) != 1:
            return (None, None)
        else:
            # Example of result data:
            # [('dn', {'accessPolicy': ['value']})]
            listdn = result[0][0]
            listpolicy = result[0][1]['accessPolicy'][0]
            returnVal = (listdn, listpolicy)

            logging.debug('__get_access_policy (returned): %s' % str(returnVal))
            return returnVal

    def __get_allowed_senders(self, listdn, listname, listpolicy, sender=''):
        """return search_result_list_based_on_access_policy"""
        logging.debug('__get_allowed_senders (listpolicy): %s' % listpolicy)

        # Set search base dn, scope, filter and attribute list based on access policy.
        if listpolicy == 'membersOnly':
            baseDN = self.baseDN
            searchScope = ldap.SCOPE_SUBTREE
            # Filter used to get domain members.
            searchFilter = '(&(objectClass=mailUser)(accountStatus=active)(enabledService=mail)(enabledService=deliver)(memberOfGroup=%s)(mail=%(sender)s))' % (listname, sender)
            searchAttrs = ['mail']
        else:
            baseDN = listdn
            searchScope = ldap.SCOPE_BASE   # Use SCOPE_BASE to improve performance.
            # Filter used to get domain moderators.
            searchFilter = '(&(objectclass=mailList)(accountStatus=active)(enabledService=mail)(enabledService=deliver)(mail=%s)(listAllowedUser=%s))' % (listname, sender)
            searchAttrs = ['listAllowedUser']

        logging.debug('__get_allowed_senders (baseDN): %s' % baseDN)
        logging.debug('__get_allowed_senders (searchScope): %s' % searchScope)
        logging.debug('__get_allowed_senders (searchFilter): %s' % searchFilter)

        try:
            result = self.conn.search_s(baseDN, searchScope, searchFilter, searchAttrs)
            logging.debug('__get_allowed_senders (search result): %s' % str(result))
        except ldap.NO_SUCH_OBJECT:
            logging.debug('__get_allowed_senders (not a mail list: %s) Returned (None)' % listname)
            return None
        except Exception, e:
            logging.debug('__get_allowed_senders (ERROR while searching list): %s' % str(e))
            return None

        if len(result) != 1:
            return None
        else:
            # Example of result data:
            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
            return result[0][1]['listAllowedUser'][0]

    def __get_smtp_action(self, listname, sender):
        """return smtp_action"""
        listdn, listpolicy = self.__get_access_policy(listname)

        logging.debug('__get_smtp_action (list_dn): %s' % listdn )
        logging.debug('__get_smtp_action (listpolicy): %s' % listpolicy )
        logging.debug('__get_smtp_action (sender): %s' % sender )

        if listdn is None or listpolicy is None:
            return None
        else:
            if listpolicy == "public":
                # No restriction.
                return ACTION_ACCEPT
            elif listpolicy == "domain":
                # Allow all users under the same domain.
                if sender.split('@')[1] == listname.split('@')[1]:
                    return ACTION_ACCEPT
                else:
                    return ACTION_REJECT
            elif listpolicy == "allowedOnly":
                # Bypass allowed users only.
                allowed_senders = self.__get_allowed_senders(listdn, listname, 'allowedOnly', sender)

                logging.debug('__get_smtp_action (allowed_senders): %s (allowedOnly)' % allowed_senders )

                if allowed_senders is not None:
                    addresses = set(allowed_senders)    # Remove duplicate addresses.
                    if sender in addresses:
                        return ACTION_ACCEPT
                    else:
                        return ACTION_REJECT
                else:
                    return ACTION_REJECT
            elif listpolicy == "membersOnly":
                allowed_senders = self.__get_allowed_senders(listdn, listname, 'membersOnly', sender)

                logging.debug('__get_smtp_action (allowed_senders): %s (membersOnly)' % allowed_senders)

                if allowed_senders is not None:
                    addresses = set(allowed_senders)
                    if sender in addresses:
                        return ACTION_ACCEPT
                    else:
                        return ACTION_REJECT
                else:
                    #return ACTION_DEFER
                    return ACTION_REJECT

    def handle_data(self, map):
        if map.has_key("sender") and map.has_key("recipient"):
            sender = map["sender"]
            recipient = map["recipient"]
            action = self.__get_smtp_action(recipient, sender)
            return action
        else:
            return ACTION_DEFER

def main():
    # Chroot in current directory.
    try:
        os.chdir(os.path.dirname(__file__))
    except:
        pass

    # Get listen address/port.
    listen_addr = cfg.get('general', 'listen_addr', '127.0.0.1')
    listen_port = int(cfg.get('general', 'listen_port', '7777'))

    run_as_daemon = cfg.get('general', 'run_as_daemon', 'yes')

    # Get log level.
    log_level = getattr(logging, cfg.get('general', 'log_level', 'info').upper())

    # Initialize file based logger.
    if cfg.get('general', 'log_type', 'file') == 'file':
        if run_as_daemon == 'yes':
            logging.basicConfig(
                    level=log_level,
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename=cfg.get('general', 'log_file', '/var/log/iredapd.log'),
                    )
        else:
            logging.basicConfig(
                    level=log_level,
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    )

    # Initialize policy daemon.
    socketDaemon = apdSocket((listen_addr, listen_port))

    # Run this program as daemon.
    if run_as_daemon == 'yes':
        daemon.daemonize()

    try:
        # Write pid number into pid file.
        f = open(cfg.get('general', 'pid_file', '/var/run/iredapd.pid'), 'w')
        f.write(str(os.getpid()))
        f.close()

        # Starting loop.
        asyncore.loop()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
