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

from libs.logger import logger
from libs import SMTP_ACTIONS
from libs.utils import is_ipv4, wildcard_ipv4, sqllist
from libs.amavisd import core as amavisd_lib
import settings

REQUIRE_AMAVISD_DB = True

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import is_local_domain
else:
    from libs.sql import is_local_domain


def get_id_of_external_addresses(conn, addresses):
    '''Return list of `mailaddr.id` of external addresses.'''
    ids = []

    if not addresses:
        logger.debug('No addresses, return empty list of ids.')
        return ids

    # Get 'mailaddr.id' of external addresses, ordered by priority
    sql = """SELECT id, email
               FROM mailaddr
              WHERE email IN %s
           ORDER BY priority DESC""" % sqllist(addresses)
    logger.debug('[SQL] Query external addresses: \n%s' % sql)

    try:
        qr = conn.execute(sql)
        qr_addresses = qr.fetchall()
    except Exception, e:
        logger.error('Error while getting list of id of external addresses: %s, SQL: %s' % (repr(e), sql))
        return ids

    if qr_addresses:
        ids = [r.id for r in qr_addresses]

    if not ids:
        # don't waste time if we don't even have senders stored in sql db.
        logger.debug('No record found in SQL database.')
        return []
    else:
        logger.debug('Addresses (in `mailaddr`): %s' % str(qr_addresses))
        return ids


def get_id_of_local_addresses(conn, addresses):
    '''Return list of `users.id` of local addresses.'''

    # Get 'users.id' of local addresses
    sql = """SELECT id, email
               FROM users
              WHERE email IN %s
           ORDER BY priority DESC""" % sqllist(addresses)
    logger.debug('[SQL] Query local addresses: \n%s' % sql)

    ids = []
    try:
        qr = conn.execute(sql)
        qr_addresses = qr.fetchall()
        if qr_addresses:
            ids = [r.id for r in qr_addresses]
    except Exception, e:
        logger.error('Error while executing SQL command: %s' % repr(e))

    if not ids:
        # don't waste time if we don't have any per-recipient wblist.
        logger.debug('No record found in SQL database.')
        return []
    else:
        logger.debug('Local addresses (in `users`): %s' % str(qr_addresses))
        return ids


def apply_inbound_wblist(conn, sender_ids, recipient_ids):
    # Return if no valid sender or recipient id.
    if not (sender_ids and recipient_ids):
        logger.debug('No valid sender id or recipient id.')
        return SMTP_ACTIONS['default']

    # Get wblist
    sql = """SELECT rid, sid, wb
               FROM wblist
              WHERE sid IN %s AND rid IN %s""" % (sqllist(sender_ids), sqllist(recipient_ids))
    logger.debug('[SQL] Query inbound wblist (in `wblist`): \n%s' % sql)
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logger.debug('No wblist found.')
        return SMTP_ACTIONS['default']

    logger.debug('Found inbound wblist: %s' % str(wblists))

    # Check sender addresses
    # rids/recipients are orded by priority
    for rid in recipient_ids:
        # sids/senders are sorted by priority
        for sid in sender_ids:
            if (rid, sid, 'W') in wblists:
                return SMTP_ACTIONS['accept'] + " wblist=(%d, %d, 'W')" % (rid, sid)

            if (rid, sid, 'B') in wblists:
                logger.info("Blacklisted: wblist=(%d, %d, 'B')" % (rid, sid))
                return SMTP_ACTIONS['reject_blacklisted']

    return SMTP_ACTIONS['default']


def apply_outbound_wblist(conn, sender_ids, recipient_ids):
    # Return if no valid sender or recipient id.
    if not (sender_ids and recipient_ids):
        logger.debug('No valid sender id or recipient id.')
        return SMTP_ACTIONS['default']

    # Bypass outgoing emails.
    if settings.WBLIST_BYPASS_OUTGOING_EMAIL:
        logger.debug('Bypass outgoing email as defined in WBLIST_BYPASS_OUTGOING_EMAIL.')
        return SMTP_ACTIONS['default']

    # Get wblist
    sql = """SELECT rid, sid, wb
               FROM outbound_wblist
              WHERE sid IN %s AND rid IN %s""" % (sqllist(sender_ids), sqllist(recipient_ids))
    logger.debug('[SQL] Query outbound wblist: \n%s' % sql)
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logger.debug('No wblist found.')
        return SMTP_ACTIONS['default']

    logger.debug('Found outbound wblist: %s' % str(wblists))

    # Check sender addresses
    # rids/recipients are orded by priority
    for sid in sender_ids:
        for rid in recipient_ids:
            if (rid, sid, 'W') in wblists:
                return SMTP_ACTIONS['accept'] + " outbound_wblist=(%d, %d, 'W')" % (rid, sid)

            if (rid, sid, 'B') in wblists:
                logger.info("Blacklisted: outbound_wblist=(%d, %d, 'B')" % (rid, sid))
                return SMTP_ACTIONS['reject_blacklisted']

    return SMTP_ACTIONS['default']


def restriction(**kwargs):
    conn = kwargs['conn_amavisd']
    conn_vmail = kwargs['conn_vmail']

    if not conn:
        logger.error('Error, no valid Amavisd database connection.')
        return SMTP_ACTIONS['default']

    # Get sender and recipient
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']

    if kwargs['sasl_username']:
        # Use sasl_username as sender for outgoing email
        sender = kwargs['sasl_username']
        sender_domain = kwargs['sasl_username_domain']

    if not sender:
        logger.debug('SKIP: no sender address.')
        return SMTP_ACTIONS['default']

    if sender == recipient:
        logger.debug('SKIP: Sender is same as recipient.')
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
    client_address = kwargs['client_address']

    valid_senders.append(client_address)
    if is_ipv4(client_address):
        valid_senders += wildcard_ipv4(client_address)

    logger.debug('Possible policy senders: %s' % str(valid_senders))
    logger.debug('Possible policy recipients: %s' % str(valid_recipients))

    # Outbound
    if kwargs['sasl_username'] or is_local_domain(conn=conn_vmail, domain=sender_domain):
        logger.debug('Apply wblist for outbound message.')

        id_of_local_addresses = get_id_of_local_addresses(conn, valid_senders)

        id_of_ext_addresses = []
        if id_of_local_addresses:
            id_of_ext_addresses = get_id_of_external_addresses(conn, valid_recipients)

        return apply_outbound_wblist(conn,
                                     sender_ids=id_of_local_addresses,
                                     recipient_ids=id_of_ext_addresses)
    else:
        logger.debug('Apply wblist for inbound message.')

        id_of_ext_addresses = []
        id_of_local_addresses = get_id_of_local_addresses(conn, valid_recipients)
        if id_of_local_addresses:
            id_of_ext_addresses = get_id_of_external_addresses(conn, valid_senders)

        return apply_inbound_wblist(conn,
                                    sender_ids=id_of_ext_addresses,
                                    recipient_ids=id_of_local_addresses)
