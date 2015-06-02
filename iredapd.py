# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import os
import sys
import pwd
import socket
import asyncore
import asynchat
import logging

from sqlalchemy import create_engine

# iRedAPD setting file and modules
import settings
from libs import __version__, SMTP_ACTIONS, daemon

# Plugin directory.
sys.path.append(os.path.abspath(os.path.dirname(__file__)) + '/plugins')

if not settings.backend in ['ldap', 'mysql', 'pgsql']:
    sys.exit('Invalid backend, it must be ldap, mysql or pgsql.')

conn_vmail = None
conn_amavisd = None
conn_iredadmin = None

if settings.backend == 'ldap':
    from libs.ldaplib.modeler import Modeler
    sql_dbn = 'mysql'

elif settings.backend in ['mysql', 'pgsql']:
    from libs.sql.modeler import Modeler

    if settings.backend == 'mysql':
        sql_dbn = 'mysql'

    elif settings.backend == 'pgsql':
        sql_dbn = 'postgres'

    uri_db_vmail = '%s://%s:%s@%s:%d/%s' % (sql_dbn,
                                            settings.sql_user,
                                            settings.sql_password,
                                            settings.sql_server,
                                            int(settings.sql_port),
                                            settings.sql_db)
    conn_vmail = create_engine(uri_db_vmail, pool_size=20, pool_recycle=3600, max_overflow=0)

try:
    uri_db_amavisd = '%s://%s:%s@%s:%d/%s' % (sql_dbn,
                                              settings.amavisd_db_user,
                                              settings.amavisd_db_password,
                                              settings.amavisd_db_server,
                                              int(settings.amavisd_db_port),
                                              settings.amavisd_db_name)

    conn_amavisd = create_engine(uri_db_amavisd, pool_size=10, pool_recycle=3600, max_overflow=0)
except:
    pass

try:
    uri_db_iredadmin = '%s://%s:%s@%s:%d/%s' % (sql_dbn,
                                                settings.iredadmin_db_user,
                                                settings.iredadmin_db_password,
                                                settings.iredadmin_db_server,
                                                int(settings.iredadmin_db_port),
                                                settings.iredadmin_db_name)

    conn_iredadmin = create_engine(uri_db_iredadmin, pool_size=10, pool_recycle=3600, max_overflow=0)
except:
    pass

class PolicyChannel(asynchat.async_chat):
    """Process each smtp policy request"""
    def __init__(self,
                 conn,
                 plugins=[],
                 sender_search_attrlist=None,
                 recipient_search_attrlist=None):
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
                conns = {'conn_vmail': conn_vmail,
                         'conn_amavisd': conn_amavisd,
                         'conn_iredadmin': conn_iredadmin}

                # Connect to Amavisd database if required
                require_amavisd_db = False
                for p in self.plugins:
                    if p.__dict__.get('REQUIRE_AMAVISD_DB', False):
                        require_amavisd_db = True
                        break

                modeler = Modeler(conns=conns,
                                  require_amavisd_db=require_amavisd_db)

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
    def __init__(self, localaddr):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(localaddr)
        self.listen(5)
        ip, port = localaddr
        logging.info("Starting iRedAPD (version: %s, backend: %s), listening on %s:%d." % (__version__, settings.backend, ip, port))

        # Load plugins.
        self.loaded_plugins = []
        for plugin in settings.plugins:
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
        conn, remote_addr = self.accept()
        logging.debug("Connect from %s, port %s." % remote_addr)

        PolicyChannel(conn,
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

    # Initialize policy daemon.
    DaemonSocket((settings.listen_address, int(settings.listen_port)))

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
