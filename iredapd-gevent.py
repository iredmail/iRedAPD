import os
import sys
import pwd
import time
from gevent.server import StreamServer
from gevent.pool import Pool

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
from libs import __version__, daemon
from libs import PLUGIN_PRIORITIES, SMTP_ACTIONS, SMTP_SESSION_ATTRIBUTES
from libs.logger import logger
from libs.utils import get_db_conn, log_policy_request

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

#
# Establish SQL database connections.
#
if settings.backend in ['mysql', 'pgsql']:
    conn_vmail = get_db_conn('vmail')
else:
    # we don't have ldap connection pool, a connection object will be
    # created in libs/ldaplib/modeler.py.
    conn_vmail = None

conn_amavisd = get_db_conn('amavisd')
conn_iredapd = get_db_conn('iredapd')

db_conns = {'conn_vmail': conn_vmail,
            'conn_amavisd': conn_amavisd,
            'conn_iredapd': conn_iredapd}

#
# Load and import enabled plugins
#
loaded_plugins = []

# Import priorities of built-in plugins.
_plugin_priorities = PLUGIN_PRIORITIES

# Import priorities of custom plugins, or custom priorities of built-in plugins
_plugin_priorities.update(settings.PLUGIN_PRIORITIES)

# If enabled plugin doesn't have a priority pre-defined, set it to 0 (lowest)
_plugins_without_priority = [i for i in settings.plugins if i not in _plugin_priorities]
for _p in _plugins_without_priority:
    _plugin_priorities[_p] = 0

# a list of {priority: name}
pnl = []
for p in settings.plugins:
    plugin_file = os.path.join(plugin_dir, p + '.py')
    if not os.path.isfile(plugin_file):
        logger.info('Plugin %s (%s) does not exist.' % (p, plugin_file))
        continue

    priority = _plugin_priorities[p]
    pnl += [{priority: p}]

# Sort plugin order with pre-defined priorities, so that we can apply
# plugins in ideal order.
ordered_plugins = []
for item in sorted(pnl, reverse=True):
    ordered_plugins += item.values()

for plugin in ordered_plugins:
    try:
        loaded_plugins.append(__import__(plugin))
        logger.info('Loading plugin (priority: %s): %s' % (_plugin_priorities[plugin], plugin))
    except Exception, e:
        logger.error('Error while loading plugin (%s): %s' % (plugin, str(e)))


#
# Get list of LDAP query attributes
#
sender_search_attrlist = []
recipient_search_attrlist = []
if settings.backend == 'ldap':
    sender_search_attrlist = ['objectClass']
    recipient_search_attrlist = ['objectClass']
    for plugin in loaded_plugins:
        try:
            sender_search_attrlist += plugin.SENDER_SEARCH_ATTRLIST
        except:
            pass

        try:
            recipient_search_attrlist += plugin.RECIPIENT_SEARCH_ATTRLIST
        except:
            pass


def policy_handle(socket, address):
    while True:
        request = socket.recv(1024)
        if not request:
            break

        lines = request.splitlines()
        if not lines:
            action = SMTP_ACTIONS['default']
            socket.send('action=' + action + '\n')
            logger.info('Client disconnected without valid input.')

        smtp_session_data = {}
        for line in lines:
            logger.debug("smtp session: " + line)

            if '=' in line:
                (key, value) = line.split('=', 1)
                if not value:
                    continue

                if key in SMTP_SESSION_ATTRIBUTES:
                    if key in ['sender', 'recipient', 'sasl_username']:
                        # convert to lower cases.
                        v = value.lower()
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
                logger.error('No result returned by modeler, fallback to default action: %s' % str(action))
                action = SMTP_ACTIONS['default']
        except Exception, e:
            action = SMTP_ACTIONS['default']
            logger.error('Unexpected error: %s. Fallback to default action: %s' % (str(e), str(action)))

        # Cleanup settings.GLOBAL_SESSION_TRACKING
        if _protocol_state == 'END-OF-MESSAGE':
            if _instance in settings.GLOBAL_SESSION_TRACKING:
                settings.GLOBAL_SESSION_TRACKING.pop(_instance)
            else:
                # Remove expired/ghost data.
                for i in settings.GLOBAL_SESSION_TRACKING:
                    if settings.GLOBAL_SESSION_TRACKING[i]['expired'] + 120 < int(time.time()):
                        settings.GLOBAL_SESSION_TRACKING

        socket.send('action=' + action + '\n')
        logger.debug('Session ended.')
        log_policy_request(smtp_session_data=smtp_session_data, action=action)

def main():
    # Set umask.
    os.umask(0077)

    # Initialize policy daemon.
    bind_address = (settings.listen_address, int(settings.listen_port))
    pool = Pool(size=100000)
    server = StreamServer(bind_address, handle=policy_handle, spawn=pool)

    # Run this program as daemon.
    try:
        daemon.daemonize(noClose=True)
        server.serve_forever()
        logger.info("""Starting iRedAPD (version: %s, backend: %s), \
                    listening on %s:%d.""" % (__version__,
                                              settings.backend,
                                              settings.listen_address,
                                              int(settings.listen_port)))
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
    os.setuid(uid)

    # Rotate log file.
    if settings.LOGROTATE_TYPE == 'size':
        logger.info("Log rotate type: size (%d MB), backup copies: %d." % ((settings.LOGROTATE_SIZE / 1024 / 1024),
                                                                           settings.LOGROTATE_COPIES))
    elif settings.LOGROTATE_TYPE == 'time':
        logger.info("Log rotate type: time, interval: %s, backup copies: %d." % (settings.LOGROTATE_INTERVAL,
                                                                                 settings.LOGROTATE_COPIES))

if __name__ == '__main__':
    main()
