# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Reject senders listed in per-user blacklists, bypass senders listed
#          in per-user whitelists stored in Amavisd database (@lookup_sql_dsn).
#
# Note: Amavisd is configured to be an after-queue content filter in iRedMail.
#       with '@lookup_sql_dsn' setting enabled in Amavisd config file, Amavisd
#       will query per-recipient, per-domain and server-wide (a.k.a. catch-all)
#       policy rules stored in SQL table `amavisd.policy`.
#
#       if you don't enable this plugin, Amavisd will quarantine emails sent
#       from per-user blacklisted senders, and no spam scanning for
#       emails sent from per-user whitelisted senders (note: other checkings
#       like banned filename, bad headers, virus are still checked - if you
#       didn't disable them in `amavisd.policy`). With this plugin,
#       we can tell Postfix to reject blacklisted sender BEFORE email enter
#       mail queue, or bypass emails directly.
#
# How to use this plugin:
#
# *) Enable `@lookup_sql_dsn` in Amavisd config file.
#
# *) Set Amavisd lookup SQL database related parameters (amavisd_db_*) in
#    iRedAPD config file `settings.py`, and enable this plugin.
#
# *) Enable iRedAPD in Postfix `smtpd_recipient_restrictions`.
#
# *) Enable this plugin in iRedAPD config file (/opt/iredapd/settings.py).
# *) Restart both iRedAPD and Postfix services.
#
# Possible white/blacklist senders:
#
#   - user@domain.com:  single sender email address
#   - @domain.com:  entire sender domain
#   - @.domain.com: entire sender domain and all sub-domains
#   - @.:           all senders
#   - 192.168.1.1:  single sender ip address
#   - 192.168.*.1:  wildcast sender ip addresses. NOTE: Any ip address field
#                   can be replaced by wildcast letter (*).

import logging
from libs import SMTP_ACTIONS, sqllist, utils
from libs.amavisd import core as amavisd_lib

# Connect to amavisd database
REQUIRE_AMAVISD_DB = True


def restriction(**kwargs):
    adb_cursor = kwargs['amavisd_db_cursor']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    client_address = kwargs['smtp_session_data']['client_address']

    if sender == recipient:
        logging.debug('Sender is same as recipient, bypassed.')
        return SMTP_ACTIONS['default']

    if not adb_cursor:
        logging.debug('Error, no valid Amavisd database connection.')
        return SMTP_ACTIONS['default']

    valid_senders = amavisd_lib.get_valid_addresses_from_email(sender, sender_domain)
    valid_recipients = amavisd_lib.get_valid_addresses_from_email(recipient, recipient_domain)

    if not valid_senders or not valid_recipients:
        logging.debug('No valid senders or recipients.')
        return SMTP_ACTIONS['default']


    # Append original IP address and all possible wildcast IP addresses
    valid_senders.append(client_address)
    if utils.is_ipv4(client_address):
        ip4 = client_address.split('.')

        ip4s = set()
        counter = 0
        for i in range(4):
            a = ip4[:]
            a[i]='*'
            ip4s.add('.'.join(a))

            if counter < 4:
                for j in range(4 - counter):
                    a[j+counter] = '*'
                    ip4s.add('.'.join(a))

            counter += 1
        valid_senders += list(ip4s)

    logging.debug('Possible policy senders: %s' % str(valid_senders))
    logging.debug('Possible policy recipients: %s' % str(valid_recipients))

    # Get 'mailaddr.id' of policy senders
    sql = """SELECT id,priority,email FROM mailaddr WHERE email IN %s ORDER BY priority DESC""" % sqllist(valid_senders)
    logging.debug('SQL: Get policy senders: %s' % sql)

    adb_cursor.execute(sql)
    senders = []
    sids = []
    for rcd in adb_cursor.fetchall():
        (id, priority, email) = rcd
        senders.append((priority, id, email))
        sids.append(id)

    if not sids:
        # don't waste time if we don't even have senders stored in sql db.
        logging.debug('No senders found in SQL database.')
        return SMTP_ACTIONS['default']

    # Sort by priority
    senders.sort()
    senders.reverse()

    logging.debug('Senders (in sql table: amavisd.mailaddr): %s' % str(senders))

    # Get 'users.id' of possible recipients
    sql = """SELECT id,priority,email FROM users WHERE email IN %s ORDER BY priority DESC""" % sqllist(valid_recipients)
    logging.debug('SQL: Get policy recipients: %s' % sql)

    adb_cursor.execute(sql)
    rcpts = []
    rids = []
    for rcd in adb_cursor.fetchall():
        (id, priority, email) = rcd
        rcpts.append((priority, id, email))
        rids.append(id)

    if not rids:
        # don't waste time if we don't have any per-recipient wblist.
        logging.debug('No recipients found in SQL database.')
        return SMTP_ACTIONS['default']

    # Sort by priority
    rcpts.sort()
    rcpts.reverse()

    logging.debug('Recipients (in sql table: amavisd.users): %s' % str(rcpts))

    # Get wblist
    sql = """SELECT rid,sid,wb FROM wblist WHERE sid IN %s AND rid IN %s""" % (sqllist(sids), sqllist(rids))
    logging.debug('SQL: Get wblist: %s' % sql)
    adb_cursor.execute(sql)
    wblists = adb_cursor.fetchall()

    if not wblists:
        # no wblist
        logging.debug('No per-recipient white/blacklist found.')
        return SMTP_ACTIONS['default']

    logging.debug('Found per-recipient white/blacklists: %s' % str(wblists))

    # Check sender addresses
    for rid in rids:    # sorted by users.priority
        for sid in sids:    # sorted by mailaddr.priority
            if (rid, sid, 'W') in wblists:
                logging.debug("Matched whitelist: wblist=(%d, %d, 'W')" % (rid, sid))
                return SMTP_ACTIONS['accept']

            if (rid, sid, 'B') in wblists:
                logging.debug("Matched blacklist: (%d, %d, 'B')" % (rid, sid))
                return SMTP_ACTIONS['reject_blacklisted']

    return SMTP_ACTIONS['default']
