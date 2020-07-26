# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import os
import sys
import pwd
import asyncore

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
from libs.channel import DaemonSocket
from libs.logger import logger

# Plugin directory.
plugin_dir = os.path.abspath(os.path.dirname(__file__)) + '/plugins'
sys.path.append(plugin_dir)

if settings.backend not in ['ldap', 'mysql', 'pgsql']:
    sys.exit("Invalid backend, it must be ldap, mysql or pgsql.")


def main():
    # Set umask.
    os.umask(0o077)

    # Establish SQL database connections.
    db_conns = utils.get_required_db_conns()

    # Initialize policy daemon.
    logger.info("Starting iRedAPD (version: {}, backend: {}), "
                "listening on {}:{}.".format(
                    __version__, settings.backend,
                    settings.listen_address, settings.listen_port))
    local_addr = (settings.listen_address, int(settings.listen_port))
    DaemonSocket(local_addr=local_addr,
                 db_conns=db_conns,
                 policy_channel='policy',
                 plugins=settings.plugins)

    if (settings.srs_secrets and settings.srs_domain):
        logger.info("Starting SRS sender rewriting channel, listening on "
                    "{}:{}".format(settings.listen_address, settings.srs_forward_port))
        local_addr = (settings.listen_address, int(settings.srs_forward_port))
        DaemonSocket(local_addr=local_addr,
                     db_conns=db_conns,
                     policy_channel='srs_sender')

        logger.info("Starting SRS recipient rewriting channel, listening on "
                    "{}:{}".format(settings.listen_address, settings.srs_reverse_port))
        local_addr = (settings.listen_address, int(settings.srs_reverse_port))
        DaemonSocket(local_addr=local_addr,
                     db_conns=db_conns,
                     policy_channel='srs_recipient')
    else:
        logger.info("No SRS domain and/or secret strings in settings.py, not loaded.")

    # Run this program as daemon.
    if '--foreground' not in sys.argv:
        try:
            daemon.daemonize(no_close=True)
        except Exception as e:
            logger.error("Error in daemon.daemonize: {}".format(repr(e)))

    # Write pid number into pid file.
    f = open(settings.pid_file, 'w')
    f.write(str(os.getpid()))
    f.close()

    # Get uid/gid of daemon user.
    p = pwd.getpwnam(settings.run_as_user)
    uid = p.pw_uid
    gid = p.pw_gid

    # Run as daemon user
    os.setgid(gid)
    os.setuid(uid)

    # Starting loop.
    try:
        if sys.version_info >= (3, 4):
            # workaround for the "Bad file descriptor" issue on Python 2.7, gh-161
            asyncore.loop(use_poll=True)
        else:
            # fixes the "Unexpected communication problem" issue on Python 2.6 and 3.0
            asyncore.loop(use_poll=False)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("Error in asyncore.loop: {}".format(repr(e)))


if __name__ == '__main__':
    main()
