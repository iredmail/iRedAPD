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

PLUGIN_DIR = os.path.abspath(os.path.dirname(__file__)) + '/plugins'
sys.path.append(PLUGIN_DIR)

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
elif backend in ['mysql', 'pgsql']:
    from libs.sqllib import SQLModeler as Modeler
else:
    sys.exit('Invalid backend. It should be ldap or sql.')

from libs import __version__, SMTP_ACTIONS


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
                modeler = Modeler(cfg=cfg, logger=logging)

                result = modeler.handle_data(self.map)
                if result != None:
                    action = result
                else:
                    action = SMTP_ACTIONS['accept']
                logging.debug("Final action: %s." % str(result))
            except Exception, e:
                action = SMTP_ACTIONS['default']
                logging.debug('Error: %s. Use default action instead: %s' %
                        (str(e), str(action)))

            logging.info('%s -> %s, %s' %
                    (self.map['sender'], self.map['recipient'], action))
            self.push('action=' + action)
            self.push('')
            asynchat.async_chat.handle_close(self)
            logging.debug("Connection closed")
        else:
            action = SMTP_ACTIONS['defer']
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
