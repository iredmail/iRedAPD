# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import os
import sys
import pwd
import socket
import asyncore
import asynchat
import logging


# iRedAPD setting file and modules
import settings
from libs import __version__, PLUGIN_PRIORITIES, SMTP_ACTIONS, SMTP_SESSION_ATTRIBUTES, daemon
from libs.utils import get_db_conn, log_smtp_session

# Plugin directory.
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/plugins')

if not settings.backend in ['ldap', 'mysql', 'pgsql']:
    sys.exit('Invalid backend, it must be ldap, mysql or pgsql.')

if settings.backend == 'ldap':
    from libs.ldaplib.modeler import Modeler

elif settings.backend in ['mysql', 'pgsql']:
    from libs.sql.modeler import Modeler


class PolicyChannel(asynchat.async_chat):
    """Process each smtp policy request"""
    def __init__(self,
                 sock,
                 db_conns=None,
                 plugins=[],
                 sender_search_attrlist=None,
                 recipient_search_attrlist=None):
        asynchat.async_chat.__init__(self, sock)
        self.buffer = []
        self.smtp_session_data = {}
        self.set_terminator('\n')

        self.db_conns = db_conns
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

                if key in SMTP_SESSION_ATTRIBUTES:
                    self.smtp_session_data[key] = value
                else:
                    logging.debug('Drop invalid smtp session attribute/value: %s' % line)

        elif len(self.smtp_session_data) != 0:
            # Log smtp session in SQL db.
            try:
                conn_iredapd = self.db_conns['conn_iredapd']
                log_smtp_session(conn=conn_iredapd, smtp_session_data=self.smtp_session_data)
            except Exception, e:
                pass

            try:
                modeler = Modeler(conns=self.db_conns)
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
                logging.error('Unexpected error: %s. Fallback to default action: %s' % (str(e), str(action)))

            # Log final action.
            logging.info('[%s] %s, %s -> %s, %s' % (self.smtp_session_data['client_address'],
                                                    self.smtp_session_data['protocol_state'],
                                                    self.smtp_session_data['sender'],
                                                    self.smtp_session_data['recipient'],
                                                    action))

            self.push('action=' + action + '\n')
            logging.debug("Session ended")
        else:
            action = SMTP_ACTIONS['default']
            logging.debug("replying: " + action)
            self.push('action=' + action + '\n')
            logging.debug("Session ended")


class DaemonSocket(asyncore.dispatcher):
    """Create socket daemon"""
    def __init__(self, local_addr, db_conns):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(local_addr)
        self.listen(5)
        ip, port = local_addr
        self.db_conns = db_conns

        logging.info("Starting iRedAPD (version: %s, backend: %s), listening on %s:%d." % (__version__, settings.backend, ip, port))

        # Load plugins.
        self.loaded_plugins = []

        # Sort plugin order with pre-defined priorities, so that we can apply
        # plugins in ideal order.
        ordered_plugins = []

        swapped_plugin_name_order = {}
        for i in PLUGIN_PRIORITIES:
            swapped_plugin_name_order[PLUGIN_PRIORITIES[i]] = i

        po = {}
        for p in settings.plugins:
            po[PLUGIN_PRIORITIES[p]] = p

        ordered_plugins = [swapped_plugin_name_order[order] for order in sorted(po)]

        for plugin in ordered_plugins:
            try:
                self.loaded_plugins.append(__import__(plugin))
                logging.info('Loading plugin: %s' % plugin)
            except Exception, e:
                logging.error('Error while loading plugin (%s): %s' % (plugin, str(e)))

        self.sender_search_attrlist = []
        self.recipient_search_attrlist = []
        if settings.backend == 'ldap':
            self.sender_search_attrlist = ['objectClass']
            self.recipient_search_attrlist = ['objectClass']
            for plugin in self.loaded_plugins:
                try:
                    self.sender_search_attrlist += plugin.SENDER_SEARCH_ATTRLIST
                except:
                    pass

                try:
                    self.recipient_search_attrlist += plugin.RECIPIENT_SEARCH_ATTRLIST
                except:
                    pass

    def handle_accept(self):
        sock, remote_addr = self.accept()
        logging.debug("Connect from %s, port %s." % remote_addr)

        PolicyChannel(sock,
                      db_conns=self.db_conns,
                      plugins=self.loaded_plugins,
                      sender_search_attrlist=self.sender_search_attrlist,
                      recipient_search_attrlist=self.recipient_search_attrlist)


def main():
    # Set umask.
    os.umask(0077)

    # Get log level.
    log_level = getattr(logging, str(settings.log_level).upper())

    # Initialize file based logger.
    logging.basicConfig(level=log_level,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename=settings.log_file)

    if settings.backend in ['mysql', 'pgsql']:
        conn_vmail = get_db_conn('vmail')
    else:
        # we don't have ldap connection pool, a connection object will be
        # created in libs/ldaplib/modeler.py.
        conn_vmail = None

    conn_amavisd = get_db_conn('amavisd')
    conn_iredadmin = get_db_conn('iredadmin')
    conn_iredapd = get_db_conn('iredapd')

    db_conns = {'conn_vmail': conn_vmail,
                'conn_amavisd': conn_amavisd,
                'conn_iredadmin': conn_iredadmin,
                'conn_iredapd': conn_iredapd}

    # Initialize policy daemon.
    local_addr = (settings.listen_address, int(settings.listen_port))
    DaemonSocket(local_addr, db_conns)

    # Run this program as daemon.
    try:
        daemon.daemonize(noClose=True)
    except Exception, e:
        logging.error('Error in daemon.daemonize: ' + str(e))

    # Run as a low privileged user.
    uid = pwd.getpwnam(settings.run_as_user)[2]

    # Write pid number into pid file.
    f = open(settings.pid_file, 'w')
    f.write(str(os.getpid()))
    f.close()

    # Set uid.
    os.setuid(uid)

    # Starting loop.
    try:
        # There's a bug report for Python 2.6/3.0 that `use_poll=True` yields
        # some 2.5 incompatibilities:
        if (sys.version_info >= (2, 7) and sys.version_info < (2, 8)) \
           or (sys.version_info >= (3, 4)):     # if python 2.7 ...
            # workaround for the "Bad file descriptor" issue on Python 2.7, gh-161
            asyncore.loop(use_poll=True)
        else:
            # fixes the "Unexpected communication problem" issue on Python 2.6 and 3.0
            asyncore.loop(use_poll=False)

    except KeyboardInterrupt:
        pass
    except Exception, e:
        logging.error('Error in asyncore.loop: ' + str(e))

if __name__ == '__main__':
    main()
