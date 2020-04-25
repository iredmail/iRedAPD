#!/usr/bin/env python3
# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: add, delete, show whitelists/blacklists for specified local recipient.

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from libs import utils, wblist
from tools import logger

web.config.debug = False

USAGE = """Usage:

    --outbound
        Manage white/blacklist for outbound messages.

        If no '--outbound' argument, defaults to manage inbound messages.

    --account account
        Add white/blacklists for specified (local) account. Valid formats:

            - a single user: username@domain.com
            - a single domain: @domain.com
            - entire domain and all its sub-domains: @.domain.com
            - anyone: @. (the ending dot is required)

        if no '--account' argument, defaults to '@.' (anyone).

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

Sample usage:

    * Show and add server-wide whitelists or blacklists:

        # python wblist_admin.py --add --whitelist 192.168.1.10 user@example.com
        # python wblist_admin.py --add --blacklist 172.16.1.10 baduser@example.com
        # python wblist_admin.py --list --whitelist
        # python wblist_admin.py --list --blacklist

    * For per-user or per-domain whitelists and blacklists, please use option
      `--account`. for example:

        # python wblist_admin.py --account user@mydomain.com --add --whitelist 192.168.1.10 user@example.com
        # python wblist_admin.py --account user@mydomain.com --add --blacklist 172.16.1.10 baduser@example.com
        # python wblist_admin.py --account user@mydomain.com --list --whitelist
        # python wblist_admin.py --account user@mydomain.com --list --blacklist
"""

if len(sys.argv) == 1:
    print(USAGE)
    sys.exit()
elif not len(sys.argv) >= 3:
    sys.exit()

logger.info('* Establishing SQL connection.')
conn = utils.get_db_conn('amavisd')

args = [v for v in sys.argv[1:]]

#
# Parse command line arguments
#
inout_type = 'inbound'
if '--outbound' in args:
    inout_type = 'outbound'
    args.remove('--outbound')

# Get wblist account, verify whether it's hosted locally.
account = '@.'
if '--account' in args:
    # per-domain or per-user account
    index = args.index('--account')
    account = args[index + 1]

    # Remove them.
    args.pop(index)
    args.pop(index)

wb_account = account
wb_account_type = utils.is_valid_amavisd_address(wb_account)

if '@' not in account:
    sys.exit('<<< ERROR >>> Invalid account format.')

# Get wblist type.
wblist_type = ''
for_whitelist = False
for_blacklist = False
if '--whitelist' in args:
    wblist_type = 'whitelist'
    for_whitelist = True
    args.remove('--whitelist')
elif '--blacklist' in args:
    wblist_type = 'blacklist'
    for_blacklist = True
    args.remove('--blacklist')
else:
    sys.exit('No --whitelist or --blacklist specified. Exit.')

# Get action.
if '--add' in args:
    action = 'add'
    args.remove('--add')
    logger.info('* Add %s %s for account: %s' % (inout_type, wblist_type, account))
elif '--delete' in args:
    action = 'delete'
    args.remove('--delete')
    logger.info('* Delete %s %s for account: %s' % (inout_type, wblist_type, account))
elif '--delete-all' in args:
    action = 'delete-all'
    args.remove('--delete-all')
    logger.info('* Delete all %s %s for account: %s' % (inout_type, wblist_type, account))
elif '--list' in args:
    action = 'list'
    args.remove('--list')
    logger.info('* List all %s %s for account: %s' % (inout_type, wblist_type, account))
else:
    sys.exit('No --add, --delete or --list specified. Exit.')

# Get specified white/blacklists
wl = []
bl = []

# Rest of arguments are wblist senders.
wb_senders = [v.lower() for v in args if utils.is_valid_amavisd_address(v)]

if for_whitelist:
    wl = wb_senders
elif for_blacklist:
    bl = wb_senders

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
            logger.error(qr[1])
    except Exception as e:
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
            qr = wblist.delete_wblist(conn=conn,
                                      account=wb_account,
                                      wl_rcpts=wl,
                                      bl_rcpts=bl)

        if qr[0]:
            _wl_senders = qr[1]['wl_senders']
            _wl_rcpts = qr[1]['wl_rcpts']
            _bl_senders = qr[1]['bl_senders']
            _bl_rcpts = qr[1]['bl_rcpts']

            for i in set(_wl_senders):
                logger.info('- Deleted: %s' % str(i))
            for i in set(_wl_rcpts):
                logger.info('- Deleted: %s' % str(i))
            for i in set(_bl_senders):
                logger.info('- Deleted: %s' % str(i))
            for i in set(_bl_rcpts):
                logger.info('- Deleted: %s' % str(i))
        else:
            logger.error(qr[1])
    except Exception as e:
        logger.info(str(e))
elif action == 'delete-all':
    try:
        if inout_type == 'inbound':
            qr = wblist.delete_all_wblist(conn=conn,
                                          account=wb_account,
                                          wl_senders=for_whitelist,
                                          bl_senders=for_blacklist)
        else:
            # inout_type == 'outbound':
            qr = wblist.delete_all_wblist(conn=conn,
                                          account=wb_account,
                                          wl_rcpts=for_whitelist,
                                          bl_rcpts=for_blacklist)

        if not qr[0]:
            logger.error(qr[1])
    except Exception as e:
        logger.info(str(e))
else:
    # action == 'list'
    try:
        if inout_type == 'inbound':
            qr = wblist.get_account_wblist(conn=conn,
                                           account=wb_account,
                                           whitelist=for_whitelist,
                                           blacklist=for_blacklist)
        else:
            # inout_type == 'outbound'
            qr = wblist.get_account_outbound_wblist(conn=conn,
                                                    account=wb_account,
                                                    whitelist=for_whitelist,
                                                    blacklist=for_blacklist)

        if qr[0]:
            _wb = []
            if for_whitelist:
                _wb = qr[1]['whitelist']
            elif for_blacklist:
                _wb = qr[1]['blacklist']

            if _wb:
                for i in sorted(_wb):
                    print(i)
            else:
                logger.info('* No whitelist/blacklist.')
        else:
            logger.error(qr[1])
    except Exception as e:
        logger.info(str(e))
