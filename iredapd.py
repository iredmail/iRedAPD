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
    from libs.ldaplib import LDAPModeler as Modeler
elif settings.backend in ['mysql', 'pgsql']:
    from libs.sqllib import SQLModeler as Modeler
else:
    sys.exit('Invalid backend, it must be ldap, mysql or pgsql.')

from libs import __version__, SMTP_ACTIONS, daemon


class PolicyChannel(asynchat.async_chat):
    def __init__(self, conn, remote_addr):
        asynchat.async_chat.__init__(self, conn)
        self.remote_addr = remote_addr
        self.buffer = []
        self.smtp_attrs = {}
        self.set_terminator('\n')
        logging.debug("Connect from %s, port %s." % self.remote_addr)

    def push(self, msg):
        asynchat.async_chat.push(self, msg + '\n')

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        if self.buffer:
            line = self.buffer.pop()
            logging.debug("smtp session: " + line)
            if line.find('=') != -1:
                key = line.split('=')[0]
                value = line.split('=', 1)[1]
                self.smtp_attrs[key] = value
        elif len(self.smtp_attrs) != 0:
            try:
                modeler = Modeler()

                result = modeler.handle_data(self.smtp_attrs)
                if result:
                    action = result
                else:
                    action = SMTP_ACTIONS['default']
                logging.debug("Final action: %s." % str(result))
            except Exception, e:
                action = SMTP_ACTIONS['default']
                logging.debug('Error: %s. Use default action instead: %s' %
                        (str(e), str(action)))

            # Log final action.
            logging.info('[%s] %s -> %s, %s' % (self.smtp_attrs['client_address'],
                                                self.smtp_attrs['sender'],
                                                self.smtp_attrs['recipient'],
                                                action,
                                               ))

            self.push('action=' + action + '\n')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")
        else:
            action = SMTP_ACTIONS['defer']
            logging.debug("replying: " + action)
            self.push(action + '\n')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")


class DaemonSocket(asyncore.dispatcher):
    def __init__(self, localaddr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(localaddr)
        self.listen(5)
        ip, port = localaddr
        logging.info("Starting iRedAPD (version %s, %s backend), listening on %s:%d." % (__version__, settings.backend, ip, port))
        logging.info("Enabled plugin(s): %s." % (', '.join(settings.plugins)))

    def handle_accept(self):
        conn, remote_addr = self.accept()
        channel = PolicyChannel(conn, remote_addr)


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
    socket_daemon = DaemonSocket((settings.listen_address, settings.listen_port))

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
