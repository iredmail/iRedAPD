# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import os
import sys
import time
import pwd
import socket
import asyncore
import asynchat

# Always remove 'settings.pyc'.
_pyc = os.path.abspath(os.path.dirname(__file__)) + '/settings.pyc'
if os.path.exists(_pyc):
    try:
        os.remove(_pyc)
    except:
        pass

del _pyc

# Import config file (settings.py) and modules
import settings
from libs import __version__, daemon, utils
from libs import SMTP_ACTIONS, TCP_REPLIES, SMTP_SESSION_ATTRIBUTES
from libs.logger import logger

# Plugin directory.
plugin_dir = os.path.abspath(os.path.dirname(__file__)) + '/plugins'
sys.path.append(plugin_dir)

if settings.backend not in ['ldap', 'mysql', 'pgsql']:
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
                 plugins=None,
                 tcp_table_plugin=None,
                 sender_search_attrlist=None,
                 recipient_search_attrlist=None):
        asynchat.async_chat.__init__(self, sock)
        self.buffer = []
        self.smtp_session_data = {}
        self.set_terminator('\n')

        self.db_conns = db_conns
        self.plugins = plugins
        self.tcp_table_plugin = tcp_table_plugin
        self.sender_search_attrlist = sender_search_attrlist
        self.recipient_search_attrlist = recipient_search_attrlist

    def push(self, msg):
        try:
            asynchat.async_chat.push(self, msg + '\n')
        except Exception, e:
            logger.error('Error while pushing message: %s. Msg: %s' % (repr(e), repr(msg)))

    def collect_incoming_data(self, data):
        self.buffer.append(data)

    def found_terminator(self):
        if self.buffer:
            # Format received data
            line = self.buffer.pop()
            if '=' in line:
                logger.debug("smtp session: " + line)
                (k, v) = line.split('=', 1)

                if k in SMTP_SESSION_ATTRIBUTES:
                    # Convert to lower cases.
                    if k in ['sender', 'recipient', 'sasl_username',
                             'reverse_client_name']:
                        v = v.lower()
                        self.smtp_session_data[k] = v

                    # Verify email address format
                    if k in ['sender', 'recipient', 'sasl_username']:
                        if v:
                            if not utils.is_email(v):
                                # Don't waste time on invalid email addresses.
                                action = SMTP_ACTIONS['default'] + ' Error: Invalid %s address: %s' % (k, v)
                                self.push('action=' + action + '\n')

                        self.smtp_session_data[k] = v

                        # Add sender_domain, recipient_domain, sasl_username_domain
                        self.smtp_session_data[k + '_domain'] = v.split('@', 1)[-1]
                    else:
                        self.smtp_session_data[k] = v
                else:
                    logger.debug('Drop invalid smtp session input: %s' % line)

            elif line.startswith('get '):
                logger.debug('tcp request: ' + line)

                if not self.tcp_table_plugin:
                    logger.debug('No tcp table plugin loaded, SKIP.')
                    self.push(TCP_REPLIES['default'] + '\n')
                else:
                    rcpt = line.split(' ', 1)[-1]

                    try:
                        d = {'rcpt': rcpt}
                        reply = utils.apply_tcp_table_plugin(self.tcp_table_plugin, **d)
                        logger.debug('tcp request: reply => ' + reply)
                        self.push(reply)
                    except Exception, e:
                        logger.error('tcp request: Error while applying plugin: ' + repr(e))
                        self.push(TCP_REPLIES['default'] + '\n')

                logger.debug('tcp request: session ended')

        elif self.smtp_session_data:
            # Track how long a request takes
            _start_time = time.time()

            # Gather data at RCPT , data will be used at END-OF-MESSAGE
            _instance = self.smtp_session_data['instance']
            _protocol_state = self.smtp_session_data['protocol_state']

            if _protocol_state == 'RCPT':
                if _instance not in settings.GLOBAL_SESSION_TRACKING:
                    # add timestamp of tracked smtp instance, so that we can
                    # remove them after instance finished.
                    _tracking_expired = int(time.time())

                    # @processed: count of processed smtp sessions
                    settings.GLOBAL_SESSION_TRACKING[_instance] = {'processed': 0,
                                                                   'expired': _tracking_expired}
                else:
                    settings.GLOBAL_SESSION_TRACKING[_instance]['processed'] += 1

            # Call modeler and apply plugins
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
                    logger.error('No result returned by modeler, fallback to default action: %s' % str(action))
                    action = SMTP_ACTIONS['default']
            except Exception, e:
                action = SMTP_ACTIONS['default']
                logger.error('Unexpected error: %s. Fallback to default action: %s' % (str(e), str(action)))

            # Remove tracking data when:
            #
            #   - if session was rejected/discard/whitelisted ('OK') during
            #     RCPT state (it never reach END-OF-MESSAGE state)
            #   - if session is in last state (END-OF-MESSAGE)
            if not action.startswith('DUNNO') or _protocol_state == 'END-OF-MESSAGE':
                if _instance in settings.GLOBAL_SESSION_TRACKING:
                    settings.GLOBAL_SESSION_TRACKING.pop(_instance)
                else:
                    # Remove expired/ghost data.
                    for i in settings.GLOBAL_SESSION_TRACKING:
                        if settings.GLOBAL_SESSION_TRACKING[i]['expired'] + 60 < int(time.time()):
                            settings.GLOBAL_SESSION_TRACKING

            self.push('action=' + action + '\n')
            logger.debug('Session ended.')

            _end_time = time.time()
            utils.log_policy_request(smtp_session_data=self.smtp_session_data,
                                     action=action,
                                     start_time=_start_time,
                                     end_time=_end_time)
        else:
            action = SMTP_ACTIONS['default']
            logger.debug("replying: " + action)
            self.push('action=' + action + '\n')
            logger.debug("Session ended")


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

        logger.info("Starting iRedAPD (version: %s, backend: %s), listening on %s:%d." % (__version__, settings.backend, ip, port))

        # Rotate log file.
        if settings.LOGROTATE_TYPE == 'size':
            logger.info("Log rotate type: size (%d MB), backup copies: %d." % ((settings.LOGROTATE_SIZE / 1024 / 1024),
                                                                               settings.LOGROTATE_COPIES))
        elif settings.LOGROTATE_TYPE == 'time':
            logger.info("Log rotate type: time, interval: %s, backup copies: %d." % (settings.LOGROTATE_INTERVAL,
                                                                                     settings.LOGROTATE_COPIES))

        # Load enabled plugins.
        qr = utils.load_enabled_plugins()
        self.loaded_plugins = qr['loaded_plugins']
        self.loaded_tcp_table_plugin = qr['loaded_tcp_table_plugin']

        # Get list of LDAP query attributes
        self.sender_search_attrlist = qr['sender_search_attrlist']
        self.recipient_search_attrlist = qr['recipient_search_attrlist']
        del qr

    def handle_accept(self):
        sock, remote_addr = self.accept()
        logger.debug("Connect from %s, port %s." % remote_addr)

        try:
            PolicyChannel(sock,
                          db_conns=self.db_conns,
                          plugins=self.loaded_plugins,
                          tcp_table_plugin=self.loaded_tcp_table_plugin,
                          sender_search_attrlist=self.sender_search_attrlist,
                          recipient_search_attrlist=self.recipient_search_attrlist)
        except Exception, e:
            logger.error('Error while applying PolicyChannel: %s' % repr(e))


def main():
    # Set umask.
    os.umask(0077)

    # Establish SQL database connections.
    db_conns = utils.get_required_db_conns()

    # Initialize policy daemon.
    local_addr = (settings.listen_address, int(settings.listen_port))
    DaemonSocket(local_addr, db_conns)

    # Run this program as daemon.
    try:
        daemon.daemonize(noClose=True)
    except Exception, e:
        logger.error('Error in daemon.daemonize: ' + str(e))

    # Write pid number into pid file.
    f = open(settings.pid_file, 'w')
    f.write(str(os.getpid()))
    f.close()

    # Get uid/gid of daemon user.
    p = pwd.getpwnam(settings.run_as_user)
    uid = p.pw_uid
    gid = p.pw_gid

    # Set log file owner
    os.chown(settings.log_file, uid, gid)
    os.chmod(settings.log_file, 0o700)

    # Run as daemon user
    os.setgid(gid)
    os.setuid(uid)

    # Create a global dict used to track smtp session data.
    #   - gather data at RCPT state
    #   - used in END-OF-MESSAGE state
    #   - clean up after applied all enabled plugins
    settings.GLOBAL_SESSION_TRACKING = {}

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
        logger.error('Error in asyncore.loop: ' + str(e))

if __name__ == '__main__':
    main()
