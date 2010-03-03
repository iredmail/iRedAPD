#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <michaelbibby (at) gmail.com>

import os
import os.path
import sys
import ConfigParser
import socket
import asyncore
import asynchat
import logging
import ldap
import daemon

__version__ = "1.2.3"

sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/plugins')

ACTION_ACCEPT = 'DUNNO'
ACTION_DEFER = 'DEFER_IF_PERMIT Service temporarily unavailable'
ACTION_REJECT = 'REJECT Not Authorized'
ACTION_DEFAULT = 'DUNNO'

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
                logging.debug('Error: %s. Use default action instead: %s' %
                        (str(e), str(action)))

            logging.info('%s -> %s, %s' %
                    (self.map['sender'], self.map['recipient'], action))
            self.push('action=' + action)
            self.push('')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")
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
        logging.info("Starting iredapd (v%s, pid: %d), listening on %s:%s." %
                (__version__, os.getpid(), ip, str(port)))

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
                logging.error('LDAP bind failed: incorrect bind dn or password.')
                sys.exit()
            except Exception, e:
                logging.error('LDAP bind failed: %s.' % str(e))
                sys.exit()

    def __get_recipient_dn_ldif(self, recipient):
        logging.debug('__get_recipient_dn_ldif (recipient): %s' % recipient)
        try:
            result = self.conn.search_s(
                    self.baseDN,
                    ldap.SCOPE_SUBTREE,
                    '(&(|(mail=%s)(shadowAddress=%s))(|(objectClass=mailUser)(objectClass=mailList)(objectClass=mailAlias)))' % (recipient, recipient),
                    )
            logging.debug('__get_recipient_dn_ldif (result): %s' % str(result))
            return (result[0][0], result[0][1])
        except Exception, e:
            logging.debug('!!! ERROR !!! __get_recipient_dn_ldif (result): %s' % str(result))
            return (None, None)

    def __get_access_policy(self, recipient):
        """Get access policy of mail list.

        return (dn_of_mail_list, value_of_access_policy,)"""

        logging.debug('__get_access_policy (list): %s' % recipient)

        # Replace 'recipient' placehold in config file with mail list address.
        try:
            cfg.set('ldap', "recipient", recipient)
        except Exception, e:
            logging.error("""Error while replacing 'recipient': %s""" % (str(e)))

        # Search mail list object.
        searchBasedn = 'mail=%s,ou=Groups,domainName=%s,%s' % (recipient, recipient.split('@')[1], self.baseDN)
        searchScope = ldap.SCOPE_BASE
        searchFilter = cfg.get('ldap', 'filter_maillist')
        searchAttr = cfg.get('ldap', 'attr_access_policy', 'accessPolicy')

        logging.debug('__get_access_policy (searchBasedn): %s' % searchBasedn)
        logging.debug('__get_access_policy (searchScope): %s' % searchScope)
        logging.debug('__get_access_policy (searchFilter): %s' % searchFilter)
        logging.debug('__get_access_policy (searchAttr): %s' % searchAttr)

        try:
            result = self.conn.search_s(searchBasedn, searchScope, searchFilter, [searchAttr])
            logging.debug('__get_access_policy (search result): %s' % str(result))
        except ldap.NO_SUCH_OBJECT:
            logging.debug('__get_access_policy (not a mail list: %s) Returned (None)' % recipient)
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
            listpolicy = result[0][1][searchAttr][0]
            returnVal = (listdn, listpolicy)

            logging.debug('__get_access_policy (returned): %s' % str(returnVal))
            return returnVal

    def __get_allowed_senders(self, listdn, recipient, listpolicy, sender=''):
        """return search_result_list_based_on_access_policy"""
        logging.debug('__get_allowed_senders (listpolicy): %s' % listpolicy)

        # Replace 'recipient' and 'sender' with email addresses.
        cfg.set("ldap", "recipient", recipient)
        cfg.set("ldap", "sender", sender)

        # Set search base dn, scope, filter and attribute list based on access policy.
        if listpolicy == 'membersOnly':
            baseDN = self.baseDN
            searchScope = ldap.SCOPE_SUBTREE
            # Filter used to get domain members.
            searchFilter = cfg.get("ldap", "filter_member")
            searchAttr = cfg.get("ldap", "attr_member")
        else:
            baseDN = listdn
            searchScope = ldap.SCOPE_BASE   # Use SCOPE_BASE to improve performance.
            # Filter used to get domain moderators.
            searchFilter = cfg.get("ldap", "filter_allowed_senders")
            searchAttr = cfg.get("ldap", "attr_moderator")

        logging.debug('__get_allowed_senders (baseDN): %s' % baseDN)
        logging.debug('__get_allowed_senders (searchScope): %s' % searchScope)
        logging.debug('__get_allowed_senders (searchFilter): %s' % searchFilter)
        logging.debug('__get_allowed_senders (searchAttr): %s' % searchAttr)

        try:
            result = self.conn.search_s(baseDN, searchScope, searchFilter, [searchAttr])
            logging.debug('__get_allowed_senders (search result): %s' % str(result))
        except ldap.NO_SUCH_OBJECT:
            logging.debug('__get_allowed_senders (not a mail list: %s) Returned (None)' % recipient)
            return None
        except Exception, e:
            logging.debug('__get_allowed_senders (ERROR while searching list): %s' % str(e))
            return None

        if len(result) != 1:
            return None
        else:
            # Example of result data:
            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
            return result[0][1][searchAttr]

    def __get_smtp_action(self, recipient, sender):
        """return smtp_action"""
        listdn, listpolicy = self.__get_access_policy(recipient)

        if listdn is None or listpolicy is None:
            return None
        else:
            if listpolicy == "public":
                # No restriction.
                return ACTION_ACCEPT
            elif listpolicy == "domain":
                # Allow all users under the same domain.
                if sender.split('@')[1] == recipient.split('@')[1]:
                    return ACTION_ACCEPT
                else:
                    return ACTION_REJECT
            elif listpolicy == "allowedOnly":
                # Bypass allowed users only.
                allowed_senders = self.__get_allowed_senders(listdn, recipient, 'allowedOnly', sender)

                if allowed_senders is not None:
                    addresses = set(allowed_senders)    # Remove duplicate addresses.
                    if sender in addresses:
                        return ACTION_ACCEPT
                    else:
                        return ACTION_REJECT
                else:
                    return ACTION_REJECT
            elif listpolicy == "membersOnly":
                allowed_senders = self.__get_allowed_senders(listdn, recipient, 'membersOnly', sender)

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
        if 'sender' in map.keys() and 'recipient' in map.keys():

            # Get plugin module name and convert plugin list to python list type.
            self.plugins = cfg.get('ldap', 'plugins', '')
            self.plugins = [v.strip() for v in self.plugins.split(',')]

            if len(self.plugins) > 0:

                # Get account dn and LDIF data.
                recipientDn, recipientLdif = self.__get_recipient_dn_ldif(map['recipient'])

                # Return if recipient account doesn't exist.
                if recipientDn is None or recipientLdif is None:
                    logging.debug(str(e))
                    return ACTION_DEFAULT

                #
                # Import plugin modules.
                #
                self.modules = []

                # Load plugin module.
                for plugin in self.plugins:
                    try:
                        self.modules.append(__import__(plugin))
                    except Exception, e:
                        logging.debug('Error while importing plugin module (%s): %s' % (plugin, str(e)))

                #
                # Apply plugins.
                #
                self.action = ''
                for module in self.modules:
                    try:
                        logging.debug('Apply plugin (%s).' % (module.__name__, ))
                        pluginAction = module.restriction(
                                ldapConn=self.conn,
                                ldapBaseDn=self.baseDN,
                                ldapRecipientDn=recipientDn,
                                ldapRecipientLdif=recipientLdif,
                                smtpSessionData=map,
                                )

                        logging.debug('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                        if not pluginAction.startswith('DUNNO'):
                            logging.info('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                            return pluginAction
                    except Exception, e:
                        logging.debug('Error while apply plugin (%s): %s' % (module, str(e)))

            else:
                # No plugins available.
                return 'DUNNO'
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
