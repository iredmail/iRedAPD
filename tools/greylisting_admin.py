# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Manage greylisting settings.

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from libs import ACCOUNT_PRIORITIES, utils
from tools import logger, get_db_conn

web.config.debug = False

USAGE = """Usage:

    --from <from_address>
    --to <to_address>
        Manage greylisting setting from email which is sent from <from_address>
        to <to_address>.
        
        Valid formats for both <from_address> and <to_address>:

            - a single user: username@domain.com
            - a single domain: @domain.com
            - entire domain and all its sub-domains: @.domain.com
            - anyone: @. (the ending dot is required)

        if no '--from' or '--to' argument, defaults to '@.' (anyone).

    --enable
        Explicitly enable greylisting for specified account.

    --disable
        Explicitly disable greylisting for specified account.

    --delete
        Delete ID of greylisting setting. You can get the value of ID by
        running this script with '--list' argument.

    --list
        Show ALL existing greylisting settings.

Sample usages:

    * Enable greylisting for emails which are sent
      from anyone to local mail domain 'example.com'

        $ python greylisting_admin.py --enable --to '@example.com'

    * Disable greylisting for emails which are sent
      from anyone to local mail user 'user@example.com'

        $ python greylisting_admin.py --disable --to 'user@example.com'

    * Disable greylisting for emails which are sent
      from 'gmail.com' to local mail user 'user@example.com'

        $ python greylisting_admin.py --disable --from '@gmail.com' --to 'user@example.com'

    * Delete greylisting setting for emails which are sent
      from anyone to local domain 'test.com

        $ python greylisting_admin.py --delete --to '@test.com'

    * List all existing greylisting settings

        $ python greylisting_admin.py --list
"""

if len(sys.argv) == 1:
    print USAGE
    sys.exit()


def delete_setting(conn, sender, rcpt):
    try:
        # Delete existing record first.
        conn.delete('greylisting',
                    vars={'account': rcpt, 'sender': sender},
                    where='account = $account AND sender = $sender')
    except Exception, e:
        logger.error(str(e))


args = [v for v in sys.argv[1:]]

#
# Parse command line arguments
#
# Get action.
if '--enable' in args:
    action = 'enable'
    args.remove('--enable')
elif '--disable' in args:
    action = 'disable'
    args.remove('--disable')
elif '--delete' in args:
    action = 'delete'
    args.remove('--delete')
elif '--list' in args:
    action = 'list'
    args.remove('--list')
else:
    sys.exit('<<< ERROR >>> No valid operation specified. Exit.')

# Get sender/recipient.
sender = '@.'
if '--from' in args:
    # per-domain or per-user account
    index = args.index('--from')
    sender = args[index + 1]

    # Remove them.
    args.pop(index)
    args.pop(index)

rcpt = '@.'
if '--to' in args:
    # per-domain or per-user account
    index = args.index('--to')
    rcpt = args[index + 1]

    # Remove them.
    args.pop(index)
    args.pop(index)

if not '@' in sender:
    sys.exit('<<< ERROR >>> Invalid sender address.')

if not '@' in rcpt:
    sys.exit('<<< ERROR >>> Invalid recipient address.')

conn = get_db_conn('iredapd')

if action in ['enable', 'disable', 'delete']:
    sender_type = utils.is_valid_amavisd_address(sender)
    rcpt_type = utils.is_valid_amavisd_address(rcpt)

    sender_priority = ACCOUNT_PRIORITIES.get(sender_type, 0)
    rcpt_priority = ACCOUNT_PRIORITIES.get(rcpt_type, 0)

    gl_setting = {'account': rcpt,
                  'priority': rcpt_priority,
                  'sender': sender,
                  'sender_priority': sender_priority}

    # Delete existing setting first.
    delete_setting(conn=conn, sender=sender, rcpt=rcpt)

# Perform the operations
if action == 'enable':
    try:
        logger.info('* Enable greylisting: %s -> %s' % (sender, rcpt))

        gl_setting['active'] = 1
        conn.insert('greylisting', **gl_setting)
    except Exception, e:
        logger.info(str(e))

elif action == 'disable':
    try:
        logger.info('* Disable greylisting: %s -> %s' % (sender, rcpt))

        gl_setting['active'] = 0
        conn.insert('greylisting', **gl_setting)
    except Exception, e:
        logger.info(str(e))

elif action == 'delete':
    try:
        logger.info('* Delete greylisting setting: %s -> %s' % (sender, rcpt))
    except Exception, e:
        logger.info(str(e))
else:
    # show existing greylisting settings.
    try:
        qr = conn.select('greylisting', order='priority DESC, sender_priority DESC')
        if qr:
            output_format = '%-36s -> %-36s %-8s'
            print output_format % ('Sender', 'Local Account', 'Status')
            print '-' * 78

        for i in qr:
            _account = i.account
            _sender = i.sender
            _active = i.active
            _comment = i.comment

            if _sender == '@.':
                _sender = '@. (anyone)'

            if _account == '@.':
                _account = '@. (anyone)'

            if _active:
                print output_format % (_sender, _account, 'enabled')
            else:
                print output_format % (_sender, _account, 'disabled')

    except Exception, e:
        logger.info(str(e))
