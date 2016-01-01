# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: add, delete, show whitelists/blacklists for specified local recipient.

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from libs import utils, wblist
from tools import logger, get_db_conn

web.config.debug = False

USAGE = """Usage:

    --outbound
        Manage white/blacklist for outbound messages.

        If no '--outbound' argument, defaults to manage inbound messages.

    --account account
        Add white/blacklists for specified (local) account. Valid formats:
            - a single user: username@domain.com
            - a single domain: domain.com

        if no '--account' argument, defaults to manage server-wide white/blacklists.

    --add
        Add white/blacklists for specified (local) account.

    --delete
        Delete specified white/blacklists for specified (local) account.

    --delete-all
        Delete ALL white/blacklists for specified (local) account.

    --list
        Show existing white/blacklists for specified (local) account. If no
        account specified, defaults to manage server-wide white/blacklists.

    --whitelist sender1 [sender2 sender3 ...]
        Whitelist specified sender(s). Multiple senders must be separated by a space.

    --blacklist sender1 [sender2 sender3 ...]
        Blacklist specified sender(s). Multiple senders must be separated by a space.

    WARNING: Do not use --list, --add-whitelist, --add-blacklist at the same time.

    --silent
        Don't ask to confirm.

Sample usage:

    * Add server-wide whitelists or blacklists, and show existing ones:

        $ python wblist_admin.py --add --whitelist 192.168.1.10 zhb@iredmail.org
        $ python wblist_admin.py --add --blacklist 172.16.1.10 bad@iredmail.org
        $ python wblist_admin.py --list --whitelist
        $ python wblist_admin.py --list --blacklist

    * Add per-user whitelists or blacklists, and show existing ones:

        $ python wblist_admin.py --account user@domain.com --add --whitelist 192.168.1.10 zhb@iredmail.org
        $ python wblist_admin.py --account user@domain.com --add --blacklist 172.16.1.10 bad@iredmail.org
        $ python wblist_admin.py --account user@domain.com --list --whitelist
        $ python wblist_admin.py --account user@domain.com --list --blacklist
"""

if len(sys.argv) == 1:
    print USAGE
    sys.exit()
elif not len(sys.argv) >= 3:
    sys.exit()

logger.info('* Establishing SQL connection.')
conn = get_db_conn('amavisd')

args = [v for v in sys.argv[1:]]

#
# Parse command line arguments
#
inout_type = 'inbound'
if '--outbound' in args:
    inout_type = 'outbound'
    args.remove('--outbound')

# Get wblist account, verify whether it's hosted locally.
if '--account' in args:
    # per-domain or per-user account
    index = args.index('--account')
    account = args[index + 1]

    # Remove them.
    args.pop(index)
    args.pop(index)

    wb_account = account
    if utils.is_email(account):
        # email
        wb_account = account
    elif utils.is_domain(account):
        # domain
        wb_account = '@' + account

    wb_account_type = utils.is_valid_amavisd_address(wb_account)
    logger.info('* Manage (%s) wblist for account: %s' % (inout_type, account))
else:
    # server-wide
    wb_account = '@.'
    logger.info('* Manage server-wide (%s) wblist (no --account).' % inout_type)

# Get action.
if '--add' in args:
    action = 'add'
    args.remove('--add')
    logger.info('* Operation: add (--add).')
elif '--delete' in args:
    action = 'delete'
    args.remove('--delete')
    logger.info('* Operation: delete (--delete).')
elif '--delete-all' in args:
    action = 'delete-all'
    args.remove('--delete-all')
    logger.info('* Operation: delete (--delete-all).')
elif '--list' in args:
    action = 'list'
    args.remove('--list')
    logger.info('* Operation: show existing wblist (--list).')
else:
    sys.exit('No --add, --delete or --list specified. Exit.')

require_confirm = True
if '--silent' in args:
    require_confirm = False
    args.remove('--silent')
elif action == 'list':
    require_confirm = False

# Get wblist type.
for_whitelist = False
for_blacklist = False
if '--whitelist' in args:
    for_whitelist = True
    args.remove('--whitelist')
    logger.info('* wblist type: whitelist (--whitelist).')
elif '--blacklist' in args:
    for_blacklist = True
    args.remove('--blacklist')
    logger.info('* wblist type: blacklist (--blacklist).')
else:
    sys.exit('No --whitelist or --blacklist specified. Exit.')

# Get specified white/blacklists
wl = []
bl = []

# Rest of arguments are wblist senders.
wb_senders = [v.lower() for v in args if utils.is_valid_amavisd_address(v)]

if for_whitelist:
    wl = wb_senders
elif for_blacklist:
    bl = wb_senders

if require_confirm:
    confirm = raw_input('Continue? [y|N] ')
    if not confirm or confirm.lower() in ['n', 'no', '']:
        sys.exit('Exit.')

# Add, delete, show
if action == 'add':
    try:
        logger.info('* Add senders: %s' % ', '.join(wb_senders))

        if inout_type == 'inbound':
            qr = wblist.add_wblist(conn=conn,
                                   account=wb_account,
                                   wl_senders=wl,
                                   bl_senders=bl,
                                   flush_before_import=False)
        else:
            # inout_type == 'outbound'
            qr = wblist.add_wblist(conn=conn,
                                   account=wb_account,
                                   wl_rcpts=wl,
                                   bl_rcpts=bl,
                                   flush_before_import=False)

        if not qr[0]:
            if qr[1] == "'module' object has no attribute 'logger'":
                # safe to ignore.
                pass
            else:
                logger.error(qr[1])
    except Exception, e:
        logger.info(str(e))

elif action == 'delete':
    try:
        if inout_type == 'inbound':
            qr = wblist.delete_wblist(conn=conn,
                                      account=wb_account,
                                      wl_senders=wl,
                                      bl_senders=bl)
        else:
            # inout_type == 'outbound':
            qr = wblist.delete_wblist(account=wb_account,
                                      wl_rcpts=wl,
                                      bl_rcpts=bl)

        if not qr[0]:
            if qr[1] == "'module' object has no attribute 'logger'":
                # safe to ignore.
                pass
            else:
                logger.error(qr[1])
    except Exception, e:
        logger.info(str(e))
elif action == 'delete-all':
    logger.info('* Delete all.')
    try:
        if inout_type == 'inbound':
            qr = wblist.delete_all_wblist(account=wb_account,
                                          wl_senders=for_whitelist,
                                          bl_senders=for_blacklist)
        else:
            # inout_type == 'outbound':
            qr = wblist.delete_all_wblist(account=wb_account,
                                          wl_rcpts=for_whitelist,
                                          bl_rcpts=for_blacklist)

        if not qr[0]:
            if qr[1] == "'module' object has no attribute 'logger'":
                # safe to ignore.
                pass
            else:
                logger.error(qr[1])
    except Exception, e:
        logger.info(str(e))
else:
    # show existing wblist entries.
    try:
        if inout_type == 'inbound':
            qr_key_wl = 'whitelist'
            qr_key_bl = 'blacklist'
            qr = wblist.get_account_wblist(conn=conn,
                                           account=wb_account,
                                           whitelist=for_whitelist,
                                           blacklist=for_blacklist)
        else:
            # inout_type == 'outbound'
            qr_key_wl = 'outbound_whitelist'
            qr_key_bl = 'outbound_blacklist'
            qr = wblist.get_account_wblist(conn=conn,
                                           account=wb_account,
                                           outbound_whitelist=for_whitelist,
                                           outbound_blacklist=for_blacklist)

        if qr[0]:
            if for_whitelist:
                if qr[1][qr_key_wl]:
                    for i in sorted(qr[1][qr_key_wl]):
                        print i
                else:
                    logger.info('* No whitelist.')
            elif for_blacklist:
                if qr[1][qr_key_bl]:
                    for i in sorted(qr[1][qr_key_bl]):
                        print i
                else:
                    logger.info('* No blacklist.')
        else:
            if qr[1] == "'module' object has no attribute 'logger'":
                # safe to ignore.
                pass
            else:
                logger.error(qr[1])
    except Exception, e:
        logger.info(str(e))

if action != 'list':
    logger.info('* Done.')
