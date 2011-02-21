#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <zhb (at) iredmail.org>

import os
import os.path
import sys
import pwd
import ConfigParser
import socket
import asyncore
import asynchat
import logging
import daemon

__version__ = "1.3.4"

ACTION_ACCEPT = 'DUNNO'
ACTION_DEFER = 'DEFER_IF_PERMIT Service temporarily unavailable'
ACTION_REJECT = 'REJECT Not Authorized'
ACTION_DEFAULT = 'DUNNO'

PLUGIN_DIR = os.path.abspath(os.path.dirname(__file__)) + '/plugins-rr'
sys.path.append(PLUGIN_DIR)

# Get config file.
if len(sys.argv) != 2:
    sys.exit('Usage: %s /path/to/iredapd-rr.ini')
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
                value = line.split('=', 1)[1]
                self.map[key] = value
        elif len(self.map) != 0:
            try:
                if cfg.get('general', 'backend', 'ldap') == 'ldap':
                    modeler = LDAPModeler()
                else:
                    modeler = MySQLModeler()

                result = modeler.handle_data(self.map)
                if result != None:
                    action = result
                else:
                    action = ACTION_ACCEPT
                logging.debug("Final action: %s." % str(result))
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


class MySQLModeler:
    def __init__(self):
        import web

        # Turn off debug mode.
        web.config.debug = False

        self.db = web.database(
            dbn='mysql',
            host=cfg.get('mysql', 'server', 'localhost'),
            db=cfg.get('mysql', 'db', 'vmail'),
            user=cfg.get('mysql', 'user', 'vmail'),
            pw=cfg.get('mysql', 'password'),
        )

    def handle_data(self, map):
        if 'sender' in map.keys() and 'recipient' in map.keys():
            # Get plugin module name and convert plugin list to python list type.
            self.plugins = cfg.get('mysql', 'plugins', '')
            self.plugins = [v.strip() for v in self.plugins.split(',')]

            # Get sender, recipient.
            # Sender/recipient are used almost in all plugins, so store them
            # a dict and pass to plugins.
            senderReceiver = {
                'sender': map['sender'],
                'recipient': map['recipient'],
                'sender_domain': map['sender'].split('@')[-1],
                'recipient_domain': map['recipient'].split('@')[-1],
            }

            if len(self.plugins) > 0:
                #
                # Import plugin modules.
                #
                self.modules = []

                # Load plugin module.
                for plugin in self.plugins:
                    try:
                        self.modules.append(__import__(plugin))
                    except ImportError:
                        # Print error message if plugin module doesn't exist.
                        # Use logging.info to let admin know this critical error.
                        logging.info('Error: plugin %s/%s.py not exist.' % (PLUGIN_DIR, plugin))
                    except Exception, e:
                        logging.debug('Error while importing plugin module (%s): %s' % (plugin, str(e)))

                #
                # Apply plugins.
                #
                for module in self.modules:
                    try:
                        logging.debug('Apply plugin (%s).' % (module.__name__, ))
                        pluginAction = module.restriction(
                            dbConn=self.db,
                            senderReceiver=senderReceiver,
                            smtpSessionData=map,
                        )

                        logging.debug('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                        if not pluginAction.startswith('DUNNO'):
                            logging.info('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                            return pluginAction

                        return 'DUNNO'
                    except Exception, e:
                        logging.debug('Error while apply plugin (%s): %s' % (module, str(e)))

            else:
                # No plugins available.
                return 'DUNNO'
        else:
            return ACTION_DEFER



class LDAPModeler:
    def __init__(self):
        import ldap

        self.ldap = ldap

        # Read LDAP server settings.
        self.uri = cfg.get('ldap', 'uri', 'ldap://127.0.0.1:389')
        self.binddn = cfg.get('ldap', 'binddn')
        self.bindpw = cfg.get('ldap', 'bindpw')
        self.baseDN = cfg.get('ldap', 'basedn')

        # Initialize ldap connection.
        try:
            self.conn = self.ldap.initialize(self.uri)
            logging.debug('LDAP connection initialied success.')
        except Exception, e:
            logging.error('LDAP initialized failed: %s.' % str(e))
            sys.exit()

        # Bind to ldap server.
        if self.binddn != '' and self.bindpw != '':
            try:
                self.conn.bind_s(self.binddn, self.bindpw)
                logging.debug('LDAP bind success.')
            except self.ldap.INVALID_CREDENTIALS:
                logging.error('LDAP bind failed: incorrect bind dn or password.')
                sys.exit()
            except Exception, e:
                logging.error('LDAP bind failed: %s.' % str(e))
                sys.exit()

    def __get_sender_dn_ldif(self, sender):
        logging.debug('__get_sender_dn_ldif (sender): %s' % sender)

        if len(sender) < 6 or sender is None:
            logging.debug('__get_sender_dn_ldif: Sender is not a valid email address.')
            return (None, None)

        try:
            logging.debug('__get_sender_dn_ldif: Quering LDAP')
            result = self.conn.search_s(
                    self.baseDN,
                    self.ldap.SCOPE_SUBTREE,
                    '(&(|(mail=%s)(shadowAddress=%s))(|(objectClass=mailUser)(objectClass=mailList)(objectClass=mailAlias)))' % (sender, sender),
                    )
            logging.debug('__get_sender_dn_ldif (result): %s' % str(result))
            if len(result) == 0:
                return (None, None)
            else:
                return (result[0][0], result[0][1])
        except Exception, e:
            logging.debug('!!! ERROR !!! __get_sender_dn_ldif (result): %s' % str(e))
            return (None, None)

    def handle_data(self, map):
        if 'sender' in map.keys() and 'recipient' in map.keys():
            # Get plugin module name and convert plugin list to python list type.
            self.plugins = cfg.get('ldap', 'plugins', '')
            self.plugins = [v.strip() for v in self.plugins.split(',')]

            if len(self.plugins) > 0:

                # Get account dn and LDIF data.
                senderDN, senderLdif = self.__get_sender_dn_ldif(map['sasl_username'])

                # Return if recipient account doesn't exist.
                if senderDN is None or senderLdif is None:
                    logging.debug('Sender DN or LDIF is none.')
                    return ACTION_DEFAULT

                #
                # Import plugin modules.
                #
                self.modules = []

                # Load plugin module.
                for plugin in self.plugins:
                    try:
                        self.modules.append(__import__(plugin))
                    except ImportError:
                        # Print error message if plugin module doesn't exist.
                        # Use logging.info to let admin know this critical error.
                        logging.info('Error: plugin %s/%s.py not exist.' % (PLUGIN_DIR, plugin))
                    except Exception, e:
                        logging.debug('Error while importing plugin module (%s): %s' % (plugin, str(e)))

                #
                # Apply plugins.
                #
                for module in self.modules:
                    try:
                        logging.debug('Apply plugin (%s).' % (module.__name__, ))
                        pluginAction = module.restriction(
                            ldapConn=self.conn,
                            ldapBaseDn=self.baseDN,
                            ldapSenderDn=senderDN,
                            ldapSenderLdif=senderLdif,
                            smtpSessionData=map,
                        )

                        logging.debug('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                        if not pluginAction.startswith('DUNNO'):
                            logging.info('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                            return pluginAction

                        return 'DUNNO'
                    except Exception, e:
                        logging.debug('Error while apply plugin (%s): %s' % (module, str(e)))

            else:
                # No plugins available.
                return 'DUNNO'
        else:
            return ACTION_DEFER


def main():
    # Set umask.
    os.umask(0077)

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

    # Run as a low privileged user.
    run_as_user = cfg.get('general', 'run_as_user', 'nobody')
    uid = pwd.getpwnam(run_as_user)[2]

    try:
        # Write pid number into pid file.
        f = open(cfg.get('general', 'pid_file', '/var/run/iredapd.pid'), 'w')
        f.write(str(os.getpid()))
        f.close()

        # Set uid.
        os.setuid(uid)

        # Starting loop.
        asyncore.loop()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
