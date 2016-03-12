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

    --list-whitelist-domains
        Show ALL whitelisted sender domain names (in `greylisting_whitelist_domains`)

    --list-whitelists
        Show ALL whitelisted sender addresses (in `greylisting_whitelists`)

    --whitelist-domain
        Explicitly whitelist a sender domain for greylisting service.

        Note: you must setup a cron job to run script
        /opt/iredapd/tools/spf_to_greylist_whitelists.py to query SPF/MX/A
        DNS records and store the IP addresses/networks stored in those DNS
        records as whitelisted senders. Default interval is 10 minutes.

    --remove-whitelist-domain
        Remove whitelisted sender domain

    --list
        Show ALL existing greylisting settings.

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
        Delete specified greylisting setting.

Sample usages:

    * List all existing greylisting settings:

        # python greylisting_admin.py --list

    * List all whitelisted sender domain names:

        # python greylisting_admin.py --list-whitelist-domains

    * List all whitelisted sender addresses:

        # python greylisting_admin.py --list-whitelists

    * Whitelist a sender domain:

        # python greylisting_admin.py --whitelist-domain --from '@example.com'

    * Remove a whitelisted sender domain:

        # python greylisting_admin.py --remove-whitelist-domain --from '@example.com'

    * Enable greylisting for emails which are sent
      from anyone to local mail domain 'example.com':

        # python greylisting_admin.py --enable --to '@example.com'

    * Disable greylisting for emails which are sent
      from anyone to local mail user 'user@example.com':

        # python greylisting_admin.py --disable --to 'user@example.com'

    * Disable greylisting for emails which are sent
      from 'gmail.com' to local mail user 'user@example.com':

        # python greylisting_admin.py --disable --from '@gmail.com' --to 'user@example.com'

    * Delete greylisting setting for emails which are sent
      from anyone to local domain 'test.com':

        # python greylisting_admin.py --delete --to '@test.com'
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
elif '--whitelist-domain' in args:
    action = 'whitelist-domain'
    args.remove('--whitelist-domain')
elif '--remove-whitelist-domain' in args:
    action = 'remove-whitelist-domain'
    args.remove('--remove-whitelist-domain')
elif '--list-whitelist-domains' in args:
    action = 'list-whitelist-domains'
    args.remove('--list-whitelist-domains')
elif '--list-whitelists' in args:
    action = 'list-whitelists'
    args.remove('--list-whitelists')
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


def whitelisting_domain(conn, domain):
    # Insert domain into sql table `iredapd.greylisting_whitelist_domains`
    try:
        conn.insert('greylisting_whitelist_domains',
                    domain=domain)
    except Exception, e:
        error = str(e).lower()
        if 'duplicate key' in error or 'duplicate entry' in error:
            pass
        else:
            logger.info(str(e))


def remove_whitelisted_domain(conn, domain):
    # Delete sender domain from `iredapd.greylisting_whitelist_domains`
    # Delete its spf/mx records from `iredapd.greylisting_whitelists`
    try:
        conn.delete('greylisting_whitelist_domains', where="domain='%s'" % domain)
        conn.delete('greylisting_whitelists', where="comment='AUTO-UPDATE: %s'" % domain)
    except Exception, e:
        logger.info(str(e))

# Check whether sender address is a domain name.
sender_is_domain = False
sender_domain = ''
if utils.is_valid_amavisd_address(sender) in ['domain', 'subdomain']:
    sender_is_domain = True
    sender_domain = sender.split('@', 1)[-1]

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
        conn.delete('greylisting_whitelists',
                    where="account='%s' AND sender='%s'" % (rcpt, sender))
    except Exception, e:
        logger.info(str(e))

elif action == 'whitelist-domain':
    logger.info('* Whitelisting sender domain: %s' % sender_domain)
    whitelisting_domain(conn=conn, domain=sender_domain)

elif action == 'remove-whitelist-domain':
    logger.info('* Remove whitelisted sender domain: %s' % sender_domain)
    remove_whitelisted_domain(conn=conn, domain=sender_domain)

elif action == 'list':
    # show existing greylisting settings.
    try:
        qr = conn.select('greylisting', order='priority DESC, sender_priority DESC')
        if not qr:
            logger.info('* No whitelists.')
            sys.exit()

        output_format = '%-8s %-34s -> %-30s'
        print output_format % ('Status', 'Sender', 'Local Account')
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
                print output_format % ('enabled', _sender, _account)
            else:
                print output_format % ('disabled', _sender, _account)

    except Exception, e:
        logger.info(str(e))

elif action == 'list-whitelist-domains':
    # show whitelisted sender domain names
    try:
        qr = conn.select('greylisting_whitelist_domains', what='domain', order='domain ASC')

        for r in qr:
            logger.info(r.domain)

    except Exception, e:
        logger.info(str(e))

elif action == 'list-whitelists':
    # show whitelisted senders in `greylisting_whitelists` table.
    try:
        qr = conn.select('greylisting_whitelists', order='account ASC, sender ASC')

        for r in qr:
            logger.info('%s -> %s "%s"' % (r.sender, r.account, r.comment))

    except Exception, e:
        logger.info(str(e))
