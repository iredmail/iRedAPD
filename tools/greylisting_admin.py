#!/usr/bin/env python3
# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Manage greylisting settings.

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from libs import utils
from libs import greylisting as lib_gl
from tools import logger, get_db_conn
from libs.utils import get_db_conn as get_db_conn2

web.config.debug = False

USAGE = """Usage:

    --list-whitelist-domains
        Show ALL whitelisted sender domain names (in `greylisting_whitelist_domains`)

    --list-whitelists
        Show ALL whitelisted sender addresses (in `greylisting_whitelists` and
        `greylisting_whitelist_domain_spf`)

    --whitelist-domain
        Whitelist the IP addresses/networks in SPF record of specified sender
        domain for greylisting service. Whitelisted domain is stored in sql
        table `greylisting_whitelist_domains`.

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

    --add-whitelist
        Whitelist specified sender for greylisting service.

Sample usages:

    * List all existing greylisting settings:

        # python greylisting_admin.py --list

    * List all whitelisted sender domain names (in SQL table `greylisting_whitelist_domains`):

        # python greylisting_admin.py --list-whitelist-domains

    * List all whitelisted sender addresses:

        # python greylisting_admin.py --list-whitelists

    * Whitelist IP networks/addresses specified in sender domain:

        # python greylisting_admin.py --whitelist-domain --from '@example.com'

      This is same as:

        # python spf_to_whitelist_domains.py --submit example.com

    * Remove a whitelisted sender domain (from SQL table `greylisting_whitelist_domains`):

        # python greylisting_admin.py --remove-whitelist-domain --from '@example.com'

    * Enable greylisting for emails which are sent
      from anyone to local mail domain `example.com`:

        # python greylisting_admin.py --enable --to '@example.com'

    * Disable greylisting for emails which are sent
      from anyone to local mail user `user@example.com`:

        # python greylisting_admin.py --disable --to 'user@example.com'

    * Disable greylisting for emails which are sent
      from `gmail.com` to local mail user `user@example.com`:

        # python greylisting_admin.py --disable --from '@gmail.com' --to 'user@example.com'

    * Delete greylisting setting for emails which are sent
      from anyone to local domain `test.com`:

        # python greylisting_admin.py --delete --to '@test.com'
"""

if len(sys.argv) == 1:
    print(USAGE)
    sys.exit()


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
elif '--add-whitelist' in args:
    action = 'add-whitelist'
    args.remove('--add-whitelist')
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

if not lib_gl.is_valid_sender(sender):
    sys.exit('<<< ERROR >>> Invalid sender address.')

if '@' not in rcpt:
    sys.exit('<<< ERROR >>> Invalid recipient address.')


# Check whether sender address is a domain name.
sender_is_domain = False
sender_domain = ''
if utils.is_valid_amavisd_address(sender) in ['domain', 'subdomain']:
    sender_is_domain = True
    sender_domain = sender.split('@', 1)[-1]

# Connection cursor with web.py
conn = get_db_conn('iredapd')

# Connection cursor with SQLAlchemy
conn2 = get_db_conn2('iredapd')

gl_setting = lib_gl.get_gl_base_setting(account=rcpt, sender=sender)

# Perform the operations
if action == 'enable':
    logger.info("* Enable greylisting: {} -> {}".format(sender, rcpt))

    qr = lib_gl.enable_greylisting(conn=conn2,
                                   account=rcpt,
                                   sender=sender)
    if not qr[0]:
        logger.info(qr[1])

elif action == 'disable':
    logger.info("* Disable greylisting: {} -> {}".format(sender, rcpt))

    qr = lib_gl.disable_greylisting(conn=conn2,
                                    account=rcpt,
                                    sender=sender)

    if not qr[0]:
        logger.info(qr[1])

elif action == 'delete':
    logger.info("* Delete greylisting setting: {} -> {}".format(sender, rcpt))
    qr = lib_gl.delete_setting(conn=conn2,
                               account=rcpt,
                               sender=sender)

    if not qr[0]:
        logger.info(qr[1])

elif action == 'whitelist-domain':
    logger.info("* Whitelisting sender domain: {}".format(sender_domain))
    qr = lib_gl.add_whitelist_domain(conn=conn2, domain=sender_domain)
    if not qr[0]:
        logger.info(qr[1])

elif action == 'remove-whitelist-domain':
    logger.info("* Remove whitelisted sender domain: {}".format(sender_domain))
    lib_gl.remove_whitelisted_domain(domain=sender_domain, conn=conn2)

elif action == 'list':
    # show existing greylisting settings.
    try:
        if rcpt == '@.':
            # Show all greylisting settings
            qr = conn.select('greylisting', order='priority DESC, sender_priority DESC')
        else:
            # Show per-account greylisting settings
            qr = conn.select('greylisting',
                             vars={'account': rcpt},
                             where='account=$account',
                             order='priority DESC, sender_priority DESC')

        if not qr:
            logger.info("* No greylisting settings.")
            sys.exit()

        output_format = '%-8s %-34s -> %-30s'
        print(output_format % ('Status', 'Sender', 'Local Account'))
        print('-' * 78)

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
                print(output_format % ('enabled', _sender, _account))
            else:
                print(output_format % ('disabled', _sender, _account))

    except Exception as e:
        logger.info(repr(e))

elif action == 'list-whitelist-domains':
    # show whitelisted sender domain names
    try:
        qr = conn.select('greylisting_whitelist_domains', what='domain', order='domain ASC')

        for r in qr:
            logger.info(r.domain)

    except Exception as e:
        logger.info(repr(e))

elif action == 'list-whitelists':
    # show whitelisted senders in `greylisting_whitelists` and
    # `greylisting_whitelist_domain_spf` tables.
    try:
        qr_spf = []
        if rcpt == '@.':
            # Show global whitelists
            qr = conn.select('greylisting_whitelists', order='account ASC, sender ASC')
            qr_spf = conn.select('greylisting_whitelist_domain_spf', order='account ASC, sender ASC')
        else:
            # Show per-account whitelists
            qr = conn.select('greylisting_whitelists',
                             vars={'account': rcpt},
                             where='account=$account',
                             order='account ASC, sender ASC')

        for r in qr:
            logger.info("{} -> {}, '{}'".format(r.sender, r.account, r.comment))

        for r in qr_spf:
            logger.info("{} -> {}, '{}'".format(r.sender, r.account, r.comment))
    except Exception as e:
        logger.info(repr(e))
elif action == 'add-whitelist':
    # show whitelisted senders in `greylisting_whitelists` table.
    try:
        qr = conn.insert('greylisting_whitelists',
                         account=rcpt,
                         sender=sender)

    except Exception as e:
        logger.info(repr(e))
