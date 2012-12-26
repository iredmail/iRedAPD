# Author: Zhang Huangbin <zhb _at_ iredmail.org>

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

# Append plugin directory.
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/plugins')

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
backend = cfg.get('general', 'backend', 'ldap')

if backend == 'ldap':
    from libs.ldaplib import LDAPModeler as Modeler
    plugins = cfg.get('ldap', 'plugins', '')
elif backend in ['mysql', 'pgsql']:
    from libs.sqllib import SQLModeler as Modeler
    plugins = cfg.get('sql', 'plugins', '')
else:
    sys.exit('Invalid backend, it must be ldap, mysql or pgsql.')

from libs import __version__, SMTP_ACTIONS


class apd_channel(asynchat.async_chat):
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
                modeler = Modeler(cfg=cfg, logger=logging)

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


class apd_socket(asyncore.dispatcher):
    def __init__(self, localaddr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(localaddr)
        self.listen(5)
        ip, port = localaddr
        logging.info("Starting iRedAPD (v%s, %s)." % (__version__, backend))
        logging.info("Enabled plugin(s): %s." % (plugins))
        logging.info("Listening on %s:%d." % (ip, port))

    def handle_accept(self):
        conn, remote_addr = self.accept()
        channel = apd_channel(conn, remote_addr)


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
    socket_daemon = apd_socket((listen_addr, listen_port))

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
