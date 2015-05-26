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
    conn = kwargs['conn_amavisd']

    if not conn:
        logging.error('Error, no valid Amavisd database connection.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    recipient = kwargs['recipient']

    client_address = kwargs['smtp_session_data']['client_address']

    if sender == recipient:
        logging.debug('Sender is same as recipient, bypassed.')
        return SMTP_ACTIONS['default']

    valid_senders = amavisd_lib.get_valid_addresses_from_email(sender)
    valid_recipients = amavisd_lib.get_valid_addresses_from_email(recipient)

    # 'user@*'
    valid_recipients.append(recipient.split('@', 1)[0] + '@*')

    # Append original IP address and all possible wildcast IP addresses
    valid_senders.append(client_address)
    if utils.is_ipv4(client_address):
        ip4 = client_address.split('.')

        ip4s = set()
        counter = 0
        for i in range(4):
            a = ip4[:]
            a[i] = '*'
            ip4s.add('.'.join(a))

            if counter < 4:
                for j in range(4 - counter):
                    a[j+counter] = '*'
                    ip4s.add('.'.join(a))

            counter += 1
        valid_senders += list(ip4s)

    logging.debug('Possible policy senders: %s' % str(valid_senders))
    logging.debug('Possible policy recipients: %s' % str(valid_recipients))

    # Get 'mailaddr.id' of policy senders, ordered by priority
    sql = """SELECT id,email FROM mailaddr WHERE email IN %s ORDER BY priority DESC""" % sqllist(valid_senders)
    logging.debug('SQL: Get policy senders: %s' % sql)

    qr = conn.execute(sql)
    senders = qr.fetchall()
    sids = []
    if senders:
        sids = [r.id for r in senders]

    if not sids:
        # don't waste time if we don't even have senders stored in sql db.
        logging.debug('No senders found in SQL database.')
        return SMTP_ACTIONS['default']

    logging.debug('Senders (in sql table: amavisd.mailaddr): %s' % str(senders))

    # Get 'users.id' of possible recipients
    sql = """SELECT id,email FROM users WHERE email IN %s ORDER BY priority DESC""" % sqllist(valid_recipients)
    logging.debug('SQL: Get policy recipients: %s' % sql)

    qr = conn.execute(sql)
    rcpts = qr.fetchall()
    rids = []
    if rcpts:
        rids = [r.id for r in rcpts]

    if not rids:
        # don't waste time if we don't have any per-recipient wblist.
        logging.debug('No recipients found in SQL database.')
        return SMTP_ACTIONS['default']

    logging.debug('Recipients (in `amavisd.users`): %s' % str(rcpts))

    # Get wblist
    sql = """SELECT rid,sid,wb FROM wblist WHERE sid IN %s AND rid IN %s""" % (sqllist(sids), sqllist(rids))
    logging.debug('SQL: Get wblist: %s' % sql)
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logging.debug('No per-recipient white/blacklist found.')
        return SMTP_ACTIONS['default']

    logging.debug('Found per-recipient white/blacklists: %s' % str(wblists))

    # Check sender addresses
    # rids/recipients are orded by priority
    for rid in rids:
        # sids/senders are sorted by priority
        for sid in sids:
            if (rid, sid, 'W') in wblists:
                return SMTP_ACTIONS['accept'] + " wblist=(%d, %d, 'W')" % (rid, sid)

            if (rid, sid, 'B') in wblists:
                logging.info("Blacklisted: wblist=(%d, %d, 'B')" % (rid, sid))
                return SMTP_ACTIONS['reject_blacklisted']

    return SMTP_ACTIONS['default']
