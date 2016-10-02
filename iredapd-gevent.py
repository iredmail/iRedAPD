import os
import sys
import pwd
import time
import signal
from gevent.server import StreamServer

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
from libs import SMTP_ACTIONS, SMTP_SESSION_ATTRIBUTES
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


# Create a global dict used to track smtp session data.
#   - gather data at RCPT state
#   - used in END-OF-MESSAGE state
#   - clean up after applied all enabled plugins
settings.GLOBAL_SESSION_TRACKING = {}

# Establish SQL database connections.
db_conns = utils.get_required_db_conns()

# Load enabled plugins.
loaded_plugins = utils.load_enabled_plugins()['loaded_plugins']

# Get list of LDAP query attributes
sender_search_attrlist = utils.load_enabled_plugins()['sender_search_attrlist']
recipient_search_attrlist = utils.load_enabled_plugins()['recipient_search_attrlist']

def policy_handle(socket, address):
    # When the request handler returns, the socket used for the request will
    # be closed. Therefore, the handler must not return if the socket is still
    # in use (for example, by manually spawned greenlets).
    while True:
        try:
            request = socket.recv(1024)
            if not request:
                break

            lines = request.splitlines()
            if not lines:
                action = SMTP_ACTIONS['default']
                socket.send('action=' + action + '\n\n')
                logger.error('Client disconnected without valid input, fallback to default action: %s.' % action)
                continue

            smtp_session_data = {}
            for line in lines:
                if not line:
                    break

                logger.debug("smtp session: " + line)

                if '=' in line:
                    (key, value) = line.split('=', 1)

                    if key in SMTP_SESSION_ATTRIBUTES:
                        if key in ['sender', 'recipient', 'sasl_username']:
                            # convert to lower cases.
                            v = value.lower()
                            if v:
                                if not utils.is_email(v):
                                    # Don't waste time on invalid email addresses.
                                    action = SMTP_ACTIONS['default'] + ' Error: Invalid %s address: %s' % (key, v)
                                    socket.send('action=' + action + '\n\n')
                                    continue

                            smtp_session_data[key] = v

                            # Add sender_domain, recipient_domain, sasl_username_domain
                            smtp_session_data[key + '_domain'] = v.split('@', 1)[-1]
                        else:
                            smtp_session_data[key] = value
                    else:
                        logger.debug('Drop invalid smtp session input: %s' % line)

            # Gather data at RCPT , data will be used at END-OF-MESSAGE
            _instance = smtp_session_data['instance']
            _protocol_state = smtp_session_data['protocol_state']

            if _protocol_state == 'RCPT':
                if _instance not in settings.GLOBAL_SESSION_TRACKING:
                    # tracking data should be removed/expired in 120 seconds to
                    # avoid infinitely increased memory if some tracking data
                    # was not removed due to some reason.
                    _tracking_expired = int(time.time())

                    # @processed: count of processed smtp sessions
                    settings.GLOBAL_SESSION_TRACKING[_instance] = {'processed': 0,
                                                                   'expired': _tracking_expired}
                else:
                    settings.GLOBAL_SESSION_TRACKING[_instance]['processed'] += 1

            # Call modeler and apply plugins
            try:
                modeler = Modeler(conns=db_conns)
                result = modeler.handle_data(
                    smtp_session_data=smtp_session_data,
                    plugins=loaded_plugins,
                    sender_search_attrlist=sender_search_attrlist,
                    recipient_search_attrlist=recipient_search_attrlist,
                )
                if result:
                    action = result
                else:
                    action = SMTP_ACTIONS['default']
                    logger.error('No result returned by modeler, fallback to default action: %s' % action)
            except Exception, e:
                action = SMTP_ACTIONS['default']
                logger.error('Unexpected error (#1): %s. Fallback to default action: %s' % (repr(e), action))

            # Cleanup settings.GLOBAL_SESSION_TRACKING
            if _protocol_state == 'END-OF-MESSAGE':
                if _instance in settings.GLOBAL_SESSION_TRACKING:
                    settings.GLOBAL_SESSION_TRACKING.pop(_instance)
                else:
                    # Remove expired/ghost data.
                    for i in settings.GLOBAL_SESSION_TRACKING:
                        if settings.GLOBAL_SESSION_TRACKING[i]['expired'] + 120 < int(time.time()):
                            settings.GLOBAL_SESSION_TRACKING

            utils.log_policy_request(smtp_session_data=smtp_session_data, action=action)
        except Exception, e:
            action = SMTP_ACTIONS['default']
            logger.error('Unexpected error (#2): %s. Fallback to default action: %s' % (repr(e), action))

        socket.send('action=' + action + '\n\n')

def main():
    # Fork to run this program as daemon.
    try:
        daemon.daemonize(noClose=True)
    except Exception, e:
        logger.error('Error in daemon.daemonize: ' + repr(e))

    try:
        # Fork once to go into the background.
        pid = os.fork()
        if pid > 0:
            # Parent. Exit using os._exit(), which doesn't fire any atexit
            # functions.
            os._exit(0)

        # First child. Create a new session. os.setsid() creates the session
        # and makes this (child) process the process group leader. The process
        # is guaranteed not to have a control terminal.
        os.setsid()

        # Ignore SIGHUP
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

        # Fork a second child to ensure that the daemon never reacquires
        # a control terminal.
        pid = os.fork()
        if pid > 0:
            # Original child. Exit.
            os._exit(0)

        # This is the second child. Set the umask.
        os.umask(0077)

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
        os.setuid(uid)

        # Rotate log file.
        if settings.LOGROTATE_TYPE == 'size':
            logger.info("Log rotate type: size (%d MB), backup copies: %d." % ((settings.LOGROTATE_SIZE / 1024 / 1024),
                                                                               settings.LOGROTATE_COPIES))
        elif settings.LOGROTATE_TYPE == 'time':
            logger.info("Log rotate type: time, interval: %s, backup copies: %d." % (settings.LOGROTATE_INTERVAL,
                                                                                     settings.LOGROTATE_COPIES))
    except Exception, e:
        logger.error('Error while running in background: ' + repr(e))
        sys.exit(255)

    # Initialize policy daemon.
    try:
        bind_address = (settings.listen_address, int(settings.listen_port))

        server = StreamServer(bind_address, handle=policy_handle)

        logger.info("""Starting iRedAPD (version: %s, backend: %s), listening on %s:%d.""" % (
            __version__,
            settings.backend,
            settings.listen_address,
            int(settings.listen_port)))

        server.serve_forever()
    except Exception, e:
        logger.error('Error while looping: ' + repr(e))

if __name__ == '__main__':
    main()
