# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import os
import os.path
import sys
import pwd
import socket
import asyncore
import asynchat
import logging

import settings

# Append plugin directory.
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/plugins')

if settings.backend == 'ldap':
    from libs.ldaplib.modeler import Modeler
elif settings.backend in ['mysql', 'pgsql']:
    from libs.sql.modeler import Modeler
else:
    sys.exit('Invalid backend, it must be ldap, mysql or pgsql.')

from libs import __version__, SMTP_ACTIONS, daemon


class PolicyChannel(asynchat.async_chat):
    """Process each smtp policy request"""
    def __init__(self,
                 conn,
                 plugins=[],
                 sender_search_attrlist=None,
                 recipient_search_attrlist=None,
                ):
        asynchat.async_chat.__init__(self, conn)
        self.buffer = []
        self.smtp_session_data = {}
        self.set_terminator('\n')

        self.plugins = plugins
        self.sender_search_attrlist = sender_search_attrlist
        self.recipient_search_attrlist = recipient_search_attrlist

    def push(self, msg):
        asynchat.async_chat.push(self, msg + '\n')

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        if self.buffer:
            # Format received data
            line = self.buffer.pop()
            logging.debug("smtp session: " + line)
            if '=' in line:
                (key, value) = line.split('=', 1)
                self.smtp_session_data[key] = value
        elif len(self.smtp_session_data) != 0:
            try:
                modeler = Modeler()
                result = modeler.handle_data(
                    smtp_session_data=self.smtp_session_data,
                    plugins=self.plugins,
                    sender_search_attrlist=self.sender_search_attrlist,
                    recipient_search_attrlist=self.recipient_search_attrlist,
                )
                if result:
                    action = result
                else:
                    action = SMTP_ACTIONS['default']
            except Exception, e:
                action = SMTP_ACTIONS['default']
                logging.debug('Unexpected error: %s. Fallback to default action: %s' % (str(e), str(action)))

            # Log final action.
            logging.info('[%s] %s -> %s, %s' % (self.smtp_session_data['client_address'],
                                                self.smtp_session_data['sender'],
                                                self.smtp_session_data['recipient'],
                                                action,
                                               ))

            self.push('action=' + action + '\n')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")
        else:
            action = SMTP_ACTIONS['defer']
            logging.debug("replying: " + action)
            self.push('action=' + action + '\n')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")


class DaemonSocket(asyncore.dispatcher):
    """Create socket daemon"""
    def __init__(self, localaddr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(localaddr)
        self.listen(5)
        ip, port = localaddr
        logging.info("Starting iRedAPD (version %s, %s backend), listening on %s:%d." % (__version__, settings.backend, ip, port))

        # Load plugins.
        self.loaded_plugins = []
        for plugin in settings.plugins:
            try:
                self.loaded_plugins.append(__import__(plugin))
                logging.info('Loading plugin: %s' % plugin)
            except Exception, e:
                logging.error('Error while loading plugin (%s): %s' % (plugin, str(e)))

        self.sender_search_attrlist = ['objectClass']
        self.recipient_search_attrlist = ['objectClass']
        for plugin in self.loaded_plugins:
            self.sender_search_attrlist += plugin.SENDER_SEARCH_ATTRLIST
            self.recipient_search_attrlist += plugin.RECIPIENT_SEARCH_ATTRLIST

    def handle_accept(self):
        conn, remote_addr = self.accept()
        logging.debug("Connect from %s, port %s." % remote_addr)
        PolicyChannel(
            conn,
            plugins=self.loaded_plugins,
            sender_search_attrlist=self.sender_search_attrlist,
            recipient_search_attrlist=self.recipient_search_attrlist,
        )


def main():
    # Set umask.
    os.umask(0077)

    # Get log level.
    log_level = getattr(logging, str(settings.log_level).upper())

    # Initialize file based logger.
    if settings.log_type == 'file':
        if settings.run_as_daemon:
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s %(levelname)s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                filename=settings.log_file,
            )
        else:
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s %(levelname)s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
            )

    # Initialize policy daemon.
    DaemonSocket((settings.listen_address, settings.listen_port))

    # Run this program as daemon.
    if settings.run_as_daemon:
        daemon.daemonize()

    # Run as a low privileged user.
    uid = pwd.getpwnam(settings.run_as_user)[2]

    try:
        # Write pid number into pid file.
        f = open(settings.pid_file, 'w')
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
