# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Greylisting.
# Reference: http://greylisting.org/articles/whitepaper.shtml

"""
Quote from http://greylisting.org/articles/whitepaper.shtml
-----------------------------------------------------------

The specific methodology for a fairly basic Greylisting implementation is as
follows:

* Check if we have seen this email triplet before.

    * If we have not seen it, create a record describing it and return a
      tempfail to the sending MTA.
    * If we have seen it, and the block is not expired, return a tempfail to
      the sending MTA.
    * If we have seen it, and the block has expired, then pass the email.

* If the delivery attempt should be passed and the delivery is successful:

    * Increment the passed count on the matching row.
    * Reset the expiration time of the record to be the standard lifetime past
      the current time.

* If the delivery attempt has been temporarily failed:

    * Increment the failed count on the matching row.
    * If the sender is the special case of the null sender, do not return a
      failure after RCPT, instead wait until after the DATA phase.
"""

import time
from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS, ACCOUNT_PRIORITIES, utils, ipaddress
from libs.utils import sqllist, is_trusted_client
import settings

# Return 4xx with greylisting message to Postfix.
action_greylisting = SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE


def _check_sender_type(sender):
    # Return string of sender type: email, ipv4, ipv6, cidr, domain, subdomain, catchall, unknown
    if sender == '@.':
        return 'catchall'

    if '@' in sender:
        if sender.startswith('@.'):
            if utils.is_domain(sender.lstrip('@.')):
                return 'subdomain'
        elif sender.startswith('@'):
            if utils.is_domain(sender.lstrip('@')):
                return 'domain'
        elif utils.is_email(sender):
            return 'email'
    elif '/' in sender:
        return 'cidr'
    elif utils.is_ipv4(sender):
        return 'ipv4'
    elif utils.is_ipv6(sender):
        return 'ipv6'

    return 'unknown'


def _is_whitelisted(conn, senders, recipients, client_address):
    """Check greylisting whitelists stored in table `greylisting_whitelists`,
    returns True if is whitelisted, otherwise returns False.

    conn        -- sql connection cursor
    recipient   -- full email address of recipient
    senders     -- list of senders we should check greylisting
    """

    # query whitelists based on recipient
    sql = """SELECT id, sender
               FROM greylisting_whitelists
              WHERE account IN %s""" % sqllist(recipients)

    logger.debug('[SQL] Query greylisting whitelists: \n%s' % sql)
    qr = conn.execute(sql)
    records = qr.fetchall()

    # check whitelisted senders
    whitelists = [str(v).lower() for (_, v) in records]
    wl = set(senders) & set(whitelists)
    if wl:
        logger.debug('Sender is whitelisted: %s' % str(wl))
        return True

    # check whitelisted cidr
    _ip = ipaddress.ip_address(unicode(client_address))

    # Check IPv4.
    if _ip.version == 4:
        _cidr_start = '.'.join(client_address.split('.', 2)[:2])
        for r in records:
            (_id, _cidr) = r

            # Make sure _cidr is IPv4 network and in 'same' IP range.
            if '/' in _cidr and _cidr.startswith(_cidr_start + '.'):
                _net = ()
                try:
                    _net = ipaddress.ip_network(unicode(_cidr))
                    if _ip in _net:
                        logger.debug('Client address (IPv4) is whitelisted: (id=%d, sender=%s)' % (_id, _cidr))
                        return True
                except Exception, e:
                    logger.debug('Not an valid IP network: (id=%d, sender=%s), error: %s' % (_id, _cidr, str(e)))
    elif _ip.version == 6:
        # Check IPv6.
        for r in records:
            (_id, _cidr) = r

            # Make sure _cidr is IPv6 network
            if ':' in _cidr and '/' in _cidr:
                _net = ()
                try:
                    _net = ipaddress.ip_network(unicode(_cidr))
                    if _ip in _net:
                        logger.debug('Client address (IPv6) is whitelisted: (id=%d, sender=%s)' % (_id, _cidr))
                        return True
                except Exception, e:
                    logger.debug('Not an valid IP network: (id=%d, sender=%s), error: %s' % (_id, _cidr, str(e)))

    logger.debug('No whitelist found.')
    return False


def _should_be_greylisted_by_setting(conn, recipients, senders, client_address):
    """Check if greylisting should be applied to specified senders: True, False.

    conn -- sql connection cursor
    recipient -- full email address of recipient
    senders -- list of senders we should check greylisting
    """
    sql = """SELECT id, account, sender, sender_priority, active
               FROM greylisting
              WHERE account IN %s
              ORDER BY priority DESC, sender_priority DESC""" % sqllist(recipients)
    logger.debug('[SQL] query greylisting settings: \n%s' % sql)

    qr = conn.execute(sql)
    records = qr.fetchall()
    logger.debug('[SQL] query result: %s' % str(records))

    if not records:
        logger.debug('No setting found, greylisting is disabled for this client.')
        return False

    _ip = ipaddress.ip_address(unicode(client_address))

    if _ip.version == 4:
        _cidr_start = '.'.join(client_address.split('.', 2)[:2])

    # Found enabled/disabled greylisting setting
    for r in records:
        (_id, _account, _sender, _sender_priority, _active) = r

        _matched = False
        if _sender in senders:
            _matched = True
        else:
            # Compare client address with CIDR ip network.
            if _sender_priority == ACCOUNT_PRIORITIES['cidr']:
                # IPv4
                if _ip.version == 4 \
                   and '/' in _sender \
                   and _sender.startswith(_cidr_start + '.'):
                    _net = ()
                    try:
                        _net = ipaddress.ip_network(_sender)
                        if _ip in _net:
                            _matched = True
                    except Exception, e:
                        logger.debug('Not an valid IP network: %s (error: %s)' % (_sender, str(e)))

        if _matched:
            if _active == 1:
                logger.debug("Greylisting should be applied according to SQL record: (id=%d, account='%s', sender='%s')" % (_id, _account, _sender))
                return True
            else:
                logger.debug("Greylisting should NOT be applied according to SQL record: (id=%d, account='%s', sender='%s')" % (_id, _account, _sender))
                # return directly
                return False

    # No matched setting, turn off greylisting
    logger.debug('No matched setting, fallback to turn off greylisting.')
    return False


def _should_be_greylisted_by_tracking(conn,
                                      sender,
                                      sender_domain,
                                      recipient,
                                      recipient_domain,
                                      client_address):
    # Time of now.
    now = int(time.time())

    # timeout in seconds
    block_expired = now + settings.GREYLISTING_BLOCK_EXPIRE * 60
    unauth_triplet_expire = now + settings.GREYLISTING_UNAUTH_TRIPLET_EXPIRE * 24 * 60 * 60
    auth_triplet_expire = now + settings.GREYLISTING_AUTH_TRIPLET_EXPIRE * 24 * 60 * 60

    sender = sqlquote(sender)
    sender_domain = sqlquote(sender_domain)
    recipient = sqlquote(recipient)
    recipient_domain = sqlquote(recipient_domain)
    client_address = sqlquote(client_address)

    # Get existing tracking record
    sql = """SELECT init_time, block_expired, record_expired
               FROM greylisting_tracking
              WHERE     sender=%s
                    AND recipient=%s
                    AND client_address=%s
              LIMIT 1""" % (sender, recipient, client_address)

    logger.debug('[SQL] query greylisting tracking: \n%s' % sql)
    qr = conn.execute(sql)
    sql_record = qr.fetchone()

    if not sql_record:
        # Not record found, insert a new one.
        sql = """INSERT INTO greylisting_tracking (sender, sender_domain,
                                                   recipient, rcpt_domain,
                                                   client_address,
                                                   init_time,
                                                   block_expired, record_expired,
                                                   blocked_count)
                      VALUES (%s, %s, %s, %s, %s, %d, %d, %d, 1)""" % (sender, sender_domain,
                                                                       recipient, recipient_domain,
                                                                       client_address,
                                                                       now,
                                                                       block_expired, unauth_triplet_expire)
        logger.debug('[SQL] No tracking record found, insert a new one: \n%s' % sql)
        conn.execute(sql)
        return True

    (_init_time, _block_expired, _record_expired) = sql_record

    # Check whether tracking record expired (if cron job didn't clean up them)
    if now > _record_expired:
        # Expired, reset the tracking data.
        sql = """UPDATE greylisting_tracking
                    SET blocked_count=1, init_time=%d, block_expired=%d, record_expired=%d
                  WHERE     sender=%s
                        AND recipient=%s
                        AND client_address=%s""" % (now, block_expired, unauth_triplet_expire,
                                                    sender, recipient, client_address)
        logger.debug('[SQL] Tracking record expired, delete existing record: \n%s' % sql)
        conn.execute(sql)
        return True

    # Tracking record doesn't expire, check whether client retries too soon.
    if now < _block_expired:
        # blocking not expired
        logger.debug('Client retries too soon, greylisted again.')
        sql = """UPDATE greylisting_tracking
                    SET blocked_count=blocked_count + 1
                  WHERE     sender=%s
                        AND recipient=%s
                        AND client_address=%s""" % (sender, recipient, client_address)

        logger.debug('[SQL] Update tracking record: \n%s' % sql)
        conn.execute(sql)
        return True
    else:
        logger.debug('Host is clear to send mail.')
        if _record_expired > auth_triplet_expire:
            # Already updated expired date.
            pass
        else:
            sql = """UPDATE greylisting_tracking
                        SET record_expired=%d, passed=1
                      WHERE     sender=%s
                            AND recipient=%s
                            AND client_address=%s""" % (auth_triplet_expire,
                                                        sender, recipient, client_address)

            logger.debug('[SQL] Update expired date (%d days from now on): \n%s' % (settings.GREYLISTING_AUTH_TRIPLET_EXPIRE, sql))
            conn.execute(sql)

        return False


def restriction(**kwargs):
    # Bypass null sender (in case we don't have `reject_null_sender` plugin enabled)
    if not kwargs['sender']:
        logger.debug('Bypass greylisting for null sender.')
        return SMTP_ACTIONS['default']

    # Bypass outgoing emails.
    if kwargs['sasl_username']:
        logger.debug('Found SASL username, bypass greylisting for outbound email.')
        return SMTP_ACTIONS['default']

    client_address = kwargs['client_address']
    if is_trusted_client(client_address):
        return SMTP_ACTIONS['default']

    conn = kwargs['conn_iredapd']

    if not conn:
        logger.error('No valid database connection, fallback to default action.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    policy_recipients = [recipient, '@' + recipient_domain, '@.']
    policy_senders = [sender,
                      '@' + sender_domain,      # per-domain
                      '@.' + sender_domain,     # sub-domains
                      '@.',                     # catch-all
                      client_address]

    if utils.is_ipv4(client_address):
        # Add wildcard ip address: xx.xx.xx.*.
        policy_senders += client_address.rsplit('.', 1)[0] + '.*'

    # Check greylisting whitelists
    if _is_whitelisted(conn,
                       senders=policy_senders,
                       recipients=policy_recipients,
                       client_address=client_address):
        return SMTP_ACTIONS['default']

    # Check greylisting settings
    if _should_be_greylisted_by_setting(conn=conn,
                                        recipients=policy_recipients,
                                        senders=policy_senders,
                                        client_address=client_address):
        # check greylisting tracking.
        if _should_be_greylisted_by_tracking(conn=conn,
                                             sender=sender,
                                             sender_domain=sender_domain,
                                             recipient=recipient,
                                             recipient_domain=recipient_domain,
                                             client_address=client_address):
            return action_greylisting

    return SMTP_ACTIONS['default']
