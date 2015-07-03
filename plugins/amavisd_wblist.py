# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Reject senders listed in per-user blacklists, bypass senders listed
#          in per-user whitelists stored in Amavisd database (@lookup_sql_dsn).
#
# Note: Amavisd is configured to be an after-queue content filter in iRedMail.
#       with '@lookup_sql_dsn' setting enabled in Amavisd config file, Amavisd
#       will query per-recipient, per-domain and server-wide (a.k.a. catch-all)
#       white/blacklists and policy rules (tables: `mailaddr`, `users`,
#       `wblist`, `policy`) stored in Amavisd SQL database.
#
#       if you don't enable this plugin, Amavisd will quarantine emails sent
#       from blacklisted senders, and bypass spam scanning for emails sent from
#       whitelisted senders (note: other checkings like banned filename, bad
#       headers, virus are still checked - if you didn't disable them in
#       `amavisd.policy`). With this plugin, we can tell Postfix to reject
#       blacklisted sender BEFORE email enter mail queue, or bypass emails sent
#       from whitelisted senders directly.
#
# How to use this plugin:
#
#   *) Enable `@lookup_sql_dsn` with correct SQL account credential in Amavisd
#      config file.
#
#   *) Set Amavisd lookup SQL database related parameters (`amavisd_db_*`) in
#      iRedAPD config file `/opt/iredapd/settings.py`.
#
#   *) Enable this plugin in iRedAPD config file `/opt/iredapd/settings.py`,
#      parameter `plugins =`.
#
#   *) Restart iRedAPD service.
#
# Formats of valid white/blacklist senders:
#
#   - user@domain.com:  single sender email address
#   - @domain.com:  entire sender domain
#   - @.domain.com: entire sender domain and all sub-domains
#   - @.:           all senders
#   - 192.168.1.2:  single sender ip address
#   - 192.168.1.*, 192.168.*.2:  wildcard sender ip addresses.
#                   NOTE: if you want to use
#                   wildcard IP address like '192.*.1.2', '192.*.*.2', please
#                   set 'WBLIST_ENABLE_ALL_WILDCARD_IP = True' in
#                   /opt/iredapd/settings.py.

import logging
from libs import SMTP_ACTIONS, sqllist, utils
from libs.amavisd import core as amavisd_lib
import settings

REQUIRE_AMAVISD_DB = True


def query_external_addresses(conn, addresses):
    '''Return list of `mailaddr.id` of external addresses.'''

    # Get 'mailaddr.id' of external addresses, ordered by priority
    sql = """SELECT id, email FROM mailaddr WHERE email IN %s ORDER BY priority DESC""" % sqllist(addresses)
    logging.debug('[SQL] Query external addresses: \n%s' % sql)

    qr = conn.execute(sql)
    qr_addresses = qr.fetchall()
    ids = []
    if qr_addresses:
        ids = [r.id for r in qr_addresses]

    if not ids:
        # don't waste time if we don't even have senders stored in sql db.
        logging.debug('No record found in SQL database.')
        return []
    else:
        logging.debug('Addresses (in sql table: amavisd.mailaddr): %s' % str(qr_addresses))
        return ids


def query_local_addresses(conn, addresses):
    '''Return list of `users.id` of local addresses.'''

    # Get 'users.id' of local addresses
    sql = """SELECT id, email FROM users WHERE email IN %s ORDER BY priority DESC""" % sqllist(addresses)
    logging.debug('[SQL] Query local addresses: \n%s' % sql)

    qr = conn.execute(sql)
    qr_addresses = qr.fetchall()
    ids = []
    if qr_addresses:
        ids = [r.id for r in qr_addresses]

    if not ids:
        # don't waste time if we don't have any per-recipient wblist.
        logging.debug('No record found in SQL database.')
        return []
    else:
        logging.debug('Local addresses (in `amavisd.users`): %s' % str(qr_addresses))
        return ids


def apply_wblist_on_inbound(conn, sender_ids, recipient_ids):
    # Get wblist
    sql = """SELECT rid, sid, wb FROM wblist
             WHERE sid IN %s AND rid IN %s""" % (sqllist(sender_ids), sqllist(recipient_ids))
    logging.debug('[SQL] Query wblist (in table `amavisd.wblist`): \n%s' % sql)
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logging.debug('No per-recipient white/blacklist found.')
        return SMTP_ACTIONS['default']

    logging.debug('Found per-recipient white/blacklists: %s' % str(wblists))

    # Check sender addresses
    # rids/recipients are orded by priority
    for rid in recipient_ids:
        # sids/senders are sorted by priority
        for sid in sender_ids:
            if (rid, sid, 'W') in wblists:
                return SMTP_ACTIONS['accept'] + " wblist=(%d, %d, 'W')" % (rid, sid)

            if (rid, sid, 'B') in wblists:
                logging.info("Blacklisted: wblist=(%d, %d, 'B')" % (rid, sid))
                return SMTP_ACTIONS['reject_blacklisted']

    return SMTP_ACTIONS['default']


def apply_wblist_on_outbound(conn, sender_ids, recipient_ids):
    # Bypass outgoing emails.
    if settings.WBLIST_BYPASS_OUTGOING_EMAIL:
        logging.debug('Bypass outgoing email as defined in WBLIST_BYPASS_OUTGOING_EMAIL.')
        return SMTP_ACTIONS['default']

    # Get wblist
    sql = """SELECT rid, sid, wb
             FROM outbound_wblist WHERE sid IN %s AND rid IN %s""" % (sqllist(sender_ids), sqllist(recipient_ids))
    logging.debug('[SQL] Get wblist: \n%s' % sql)
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logging.debug('No per-recipient white/blacklist found.')
        return SMTP_ACTIONS['default']

    logging.debug('Found per-recipient white/blacklists: %s' % str(wblists))

    # Check sender addresses
    # rids/recipients are orded by priority
    for rid in recipient_ids:
        # sids/senders are sorted by priority
        for sid in sender_ids:
            if (rid, sid, 'W') in wblists:
                return SMTP_ACTIONS['accept'] + " wblist=(%d, %d, 'W')" % (rid, sid)

            if (rid, sid, 'B') in wblists:
                logging.info("Blacklisted: wblist=(%d, %d, 'B')" % (rid, sid))
                return SMTP_ACTIONS['reject_blacklisted']

    return SMTP_ACTIONS['default']


def restriction(**kwargs):
    conn = kwargs['conn_amavisd']

    if not conn:
        logging.error('Error, no valid Amavisd database connection.')
        return SMTP_ACTIONS['default']

    # Get sender
    sender = kwargs['sender']
    if kwargs['sasl_username']:
        # Use sasl_username as sender for outgoing email
        sender = kwargs['sasl_username']

    recipient = kwargs['recipient']

    if sender == recipient:
        logging.debug('Sender is same as recipient, bypassed.')
        return SMTP_ACTIONS['default']

    valid_senders = amavisd_lib.get_valid_addresses_from_email(sender)
    valid_recipients = amavisd_lib.get_valid_addresses_from_email(recipient)

    if not kwargs['sasl_username']:
        # Sender 'username@*'
        sender_username = sender.split('@', 1)[0]
        if '+' in sender_username:
            valid_senders.append(sender_username.split('+', 1)[0] + '@*')
        else:
            valid_senders.append(sender_username + '@*')

        # Append original IP address and all possible wildcast IP addresses
        client_address = kwargs['smtp_session_data']['client_address']

        valid_senders.append(client_address)
        if utils.is_ipv4(client_address):
            ip4 = client_address.split('.')

            if settings.WBLIST_ENABLE_ALL_WILDCARD_IP:
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
            else:
                # 11.22.33.*
                valid_senders.append('.'.join(ip4[:3]) + '.*')
                # 11.22.*.44
                valid_senders.append('.'.join(ip4[:2]) + '.*.' + ip4[3])

    logging.debug('Possible policy senders: %s' % str(valid_senders))
    logging.debug('Possible policy recipients: %s' % str(valid_recipients))

    if kwargs['sasl_username']:
        logging.debug('Apply wblist for outbound message.')

        id_of_ext_addresses = query_external_addresses(conn, valid_recipients)
        id_of_local_addresses = query_local_addresses(conn, valid_senders)

        return apply_wblist_on_outbound(conn,
                                        sender_ids=id_of_local_addresses,
                                        recipient_ids=id_of_ext_addresses)
    else:
        logging.debug('Apply wblist for inbound message.')

        id_of_ext_addresses = query_external_addresses(conn, valid_senders)
        id_of_local_addresses = query_local_addresses(conn, valid_recipients)

        return apply_wblist_on_inbound(conn,
                                       sender_ids=id_of_ext_addresses,
                                       recipient_ids=id_of_local_addresses)
