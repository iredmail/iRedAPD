# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Greylisting.

# TODO Support per-domain whitelisting for greylisting service.

"""
* Please read tutorial below to understand how to manage greylisting settings:
  http://www.iredmail.org/docs/manage.iredapd.html

* Understand greylisting:
  http://greylisting.org/articles/whitepaper.shtml
"""

import time
from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS, ACCOUNT_PRIORITIES
from libs import utils, ipaddress, dnsspf
import settings


# Return 4xx with greylisting message to Postfix.
action_greylisting = SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE


def _is_whitelisted(conn,
                    senders,
                    recipients,
                    client_address,
                    ip_object):
    """Check greylisting whitelists stored in table
    `greylisting_whitelists` and `greylisting_whitelist_domain_spf`,
    returns True if is whitelisted, otherwise returns False.

    @conn -- sql connection cursor
    @senders -- list of senders we should check greylisting
    @recipient -- full email address of recipient
    @client_address -- client IP address
    @ip_object -- object of IP address type (get by ipaddress.ip_address())
    """

    whitelists = []

    for tbl in ['greylisting_whitelist_domain_spf', 'greylisting_whitelists']:
        # query whitelists based on recipient
        sql = """SELECT sender
                   FROM %s
                  WHERE account IN %s""" % (tbl, sqlquote(recipients))

        logger.debug('[SQL] Query greylisting whitelists from `%s`: \n%s' % (tbl, sql))
        qr = conn.execute(sql)
        records = qr.fetchall()

        _wls = [str(v[0]).lower() for v in records]

        # check whether sender (email/domain/ip) is explicitly whitelisted
        if client_address in _wls:
            logger.info('[%s] Client IP is explictly whitelisted for greylisting service.' % (client_address))
            return True

        _wl_senders = set(senders) & set(_wls)
        if _wl_senders:
            logger.info('[%s] Sender address is explictly whitelisted for greylisting service: %s' % (client_address, ', '.join(_wl_senders)))
            return True

        whitelists += _wls

    logger.debug('[%s] Client is not explictly whitelisted.' % (client_address))

    # IPv4/v6 CIDR networks
    _cidrs = []

    # Gather CIDR networks
    if ip_object.version == 4:
        # if `ip=a.b.c.d`, ip prefix = `a.`
        _cidr_prefix = client_address.split('.', 1)[0] + '.'

        # Make sure _cidr is IPv4 network and in 'same' IP range.
        _cidrs = [_cidr for _cidr in whitelists if (_cidr.startswith(_cidr_prefix) and '/' in _cidr)]
    elif ip_object.version == 6:
        # if `ip=a:b:c:...`, ip prefix = `a:`
        _cidr_prefix = client_address.split(':', 1)[0] + ':'

        _cidrs = [_cidr for _cidr in whitelists if _cidr.startswith(_cidr_prefix) and ':/' in _cidr]

    if _cidrs:
        _net = ()
        for _cidr in _cidrs:
            try:
                _net = ipaddress.ip_network(unicode(_cidr))
                if ip_object in _net:
                    logger.info('[%s] Client network is whitelisted: cidr=%s' % (client_address, _cidr))
                    return True
            except Exception, e:
                logger.debug('Not an valid IP network: sender=%s, error=%s' % (_cidr, repr(e)))

    logger.debug('No whitelist found.')
    return False


def _client_address_passed_in_tracking(conn, client_address):
    sql = """SELECT id
               FROM greylisting_tracking
              WHERE client_address=%s AND passed=1
              LIMIT 1""" % sqlquote(client_address)

    logger.debug('[SQL] check whether client address (%s) passed greylisting: \n%s' % (client_address, sql))
    qr = conn.execute(sql)
    sql_record = qr.fetchone()

    if sql_record:
        logger.debug('Client address (%s) passed greylisting.' % client_address)
        return True
    else:
        logger.debug("Client address (%s) didn't pass greylisting." % client_address)
        return False


def _should_be_greylisted_by_setting(conn,
                                     recipients,
                                     senders,
                                     client_address,
                                     ip_object):
    """Check if greylisting should be applied to specified senders: True, False.

    conn -- sql connection cursor
    recipient -- full email address of recipient
    senders -- list of senders we should check greylisting
    client_address -- client IP address
    ip_object   -- object of IP address type (get by ipaddress.ip_address())
    """
    sql = """SELECT id, account, sender, sender_priority, active
               FROM greylisting
              WHERE account IN %s
              ORDER BY priority DESC, sender_priority DESC""" % sqlquote(recipients)
    logger.debug('[SQL] query greylisting settings: \n%s' % sql)

    qr = conn.execute(sql)
    records = qr.fetchall()
    logger.debug('[SQL] query result: %s' % str(records))

    if not records:
        logger.debug('No setting found. Disable Greylisting for this client.')
        return False

    if ip_object.version == 4:
        _cidr_prefix = client_address.split('.', 1)[0] + '.'

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
                if ip_object.version == 4 \
                   and '/' in _sender \
                   and _sender.startswith(_cidr_prefix):
                    _net = ()
                    try:
                        _net = ipaddress.ip_network(_sender)
                        if ip_object in _net:
                            _matched = True
                    except Exception, e:
                        logger.debug('Not a valid IP network: {0} (error: {1})'.format(_sender, e))

        if _matched:
            if _active == 1:
                logger.debug("Greylisting should be applied according to SQL "
                             "record: (id={0}, account='{1}', sender='{2}')".format(_id, _account, _sender))
                return True
            else:
                logger.debug("Greylisting should NOT be applied according to "
                             "SQL record: (id={0}, account='{1}', sender='{2}')".format(_id, _account, _sender))
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
    block_expired = now + int(settings.GREYLISTING_BLOCK_EXPIRE) * 60
    unauth_triplet_expire = now + int(settings.GREYLISTING_UNAUTH_TRIPLET_EXPIRE) * 24 * 60 * 60
    auth_triplet_expire = now + int(settings.GREYLISTING_AUTH_TRIPLET_EXPIRE) * 24 * 60 * 60

    sender = sqlquote(sender)
    sender_domain = sqlquote(sender_domain)
    recipient = sqlquote(recipient)
    recipient_domain = sqlquote(recipient_domain)
    client_address_sql = sqlquote(client_address)

    #
    # Get existing tracking record
    #
    # Get passed IP address.
    sql = """SELECT init_time, blocked_count, block_expired, record_expired
               FROM greylisting_tracking
              WHERE sender=%s
                    AND recipient=%s
                    AND client_address=%s
              LIMIT 1""" % (sender, recipient, client_address_sql)

    logger.debug('[SQL] query greylisting tracking: \n%s' % sql)
    try:
        qr = conn.execute(sql)
        sql_record = qr.fetchone()
    except Exception, e:
        logger.error('Error while querying greylisting tracking: %s. SQL: %s' % (repr(e), sql))

    if not sql_record:
        # Not record found, insert a new one.
        logger.info('[%s] Client has not been seen before, greylisted.' % client_address)

        sql = """INSERT INTO greylisting_tracking (sender, sender_domain,
                                                   recipient, rcpt_domain,
                                                   client_address,
                                                   init_time,
                                                   block_expired, record_expired,
                                                   blocked_count)
                      VALUES (%s, %s, %s, %s, %s, %d, %d, %d, 1)""" % (sender, sender_domain,
                                                                       recipient, recipient_domain,
                                                                       client_address_sql,
                                                                       now,
                                                                       block_expired, unauth_triplet_expire)
        logger.debug('[SQL] New tracking: \n%s' % sql)
        try:
            conn.execute(sql)
        except Exception, e:
            if e.__class__.__name__ == 'IntegrityError':
                pass
            else:
                logger.error('Error while initializing greylisting tracking: %s' % repr(e))

        return True

    (_init_time, _blocked_count, _block_expired, _record_expired) = sql_record

    # Check whether tracking record expired (if cron job didn't clean up them)
    if now > _record_expired:
        # Expired, reset the tracking data.
        logger.info('[%s] Greylisting tracking expired, update as first seen.' % client_address)

        sql = """UPDATE greylisting_tracking
                    SET blocked_count=1, init_time=%d, block_expired=%d, record_expired=%d
                  WHERE     sender=%s
                        AND recipient=%s
                        AND client_address=%s""" % (now, block_expired, unauth_triplet_expire,
                                                    sender, recipient, client_address_sql)
        logger.debug('[SQL] Update expired tracking as first seen: \n%s' % sql)
        conn.execute(sql)
        return True

    # Tracking record doesn't expire, check whether client retries too soon.
    if now < _block_expired:
        # blocking not expired
        logger.info('[%s] Client retries too soon, greylisted again.' % client_address)
        sql = """UPDATE greylisting_tracking
                    SET blocked_count=blocked_count + 1
                  WHERE     sender=%s
                        AND recipient=%s
                        AND client_address=%s""" % (sender, recipient, client_address_sql)

        logger.debug('[SQL] Update tracking record: \n%s' % sql)
        try:
            conn.execute(sql)
        except Exception, e:
            logger.error('Error while updating greylisting tracking: %s' % repr(e))
            conn.execute(sql)
            logger.error('Re-updated. It is safe to ignore above error message.')
        return True
    else:
        logger.info('[%s] Client has passed the greylisting, accept this email and whitelist client for %d days.' % (client_address, settings.GREYLISTING_AUTH_TRIPLET_EXPIRE))

        # Update expired time
        if _record_expired > auth_triplet_expire:
            # Already updated expired date.
            pass
        else:
            sql = """UPDATE greylisting_tracking
                        SET record_expired=%d, passed=1
                      WHERE     sender=%s
                            AND recipient=%s
                            AND client_address=%s""" % (auth_triplet_expire,
                                                        sender, recipient, client_address_sql)

            logger.debug('[SQL] Update expired date: \n%s' % sql)
            try:
                conn.execute(sql)
            except Exception, e:
                logger.error('[%s] Error while Updating expired date for passed client: %s' % (client_address, repr(e)))

            # Remove other tracking records from same client IP address to save
            # database space.
            sql = """DELETE FROM greylisting_tracking
                      WHERE client_address=%s AND passed=0""" % (client_address_sql)

            logger.debug('[SQL] Remove other tracking records from same client IP address: \n%s' % sql)
            try:
                conn.execute(sql)
            except Exception, e:
                logger.error('[%s] Error while removing other tracking records from passed client: %s' % (client_address, repr(e)))

        return False


def restriction(**kwargs):
    # Bypass null sender (in case we don't have `reject_null_sender` plugin enabled)
    #if not kwargs['sender']:
    #    logger.debug('Bypass greylisting for null sender.')
    #    return SMTP_ACTIONS['default']

    # Bypass outgoing emails.
    if kwargs['sasl_username']:
        logger.debug('Found SASL username, bypass greylisting for outbound email.')
        return SMTP_ACTIONS['default']

    client_address = kwargs['client_address']
    if utils.is_trusted_client(client_address):
        return SMTP_ACTIONS['default']

    sender = kwargs['sender_without_ext']
    sender_domain = kwargs['sender_domain']
    sender_tld_domain = sender_domain.split('.')[-1]
    recipient = kwargs['recipient_without_ext']
    recipient_domain = kwargs['recipient_domain']

    policy_recipients = utils.get_policy_addresses_from_email(mail=recipient)
    policy_senders = [sender,                   # email address
                      '@' + sender_domain,      # sender domain
                      '@.' + sender_domain,     # sender sub-domains
                      sender_tld_domain,        # top-level-domain
                      '@.',                     # catch-all
                      client_address]           # client IP address

    if utils.is_ipv4(client_address):
        # Add wildcard ip address: xx.xx.xx.*.
        policy_senders += client_address.rsplit('.', 1)[0] + '.*'

    # Get object of IP address type
    _ip_object = ipaddress.ip_address(unicode(client_address))

    conn_iredapd = kwargs['conn_iredapd']
    # Check greylisting whitelists
    if _is_whitelisted(conn=conn_iredapd,
                       senders=policy_senders,
                       recipients=policy_recipients,
                       client_address=client_address,
                       ip_object=_ip_object):
        return SMTP_ACTIONS['default']

    # Check greylisting settings
    if not _should_be_greylisted_by_setting(conn=conn_iredapd,
                                            recipients=policy_recipients,
                                            senders=policy_senders,
                                            client_address=client_address,
                                            ip_object=_ip_object):
        return SMTP_ACTIONS['default']

    # Bypass if sender server is listed in SPF DNS record of sender domain.
    if settings.GREYLISTING_BYPASS_SPF:
        if dnsspf.is_allowed_server_in_spf(sender_domain=sender_domain, ip=client_address):
            logger.info('Bypass greylisting. Sender server {0} is listed in '
                        'SPF DNS record of sender domain '
                        '({1}).'.format(client_address, sender_domain))
            return SMTP_ACTIONS['default']

    if _client_address_passed_in_tracking(conn=conn_iredapd, client_address=client_address):
        # Update expire time
        _now = int(time.time())
        _new_expire_time = _now + settings.GREYLISTING_AUTH_TRIPLET_EXPIRE * 24 * 60 * 60
        _sql = """UPDATE greylisting_tracking
                     SET record_expired=%d
                   WHERE client_address=%s AND passed=1""" % (_new_expire_time, sqlquote(client_address))
        logger.debug('[SQL] Update expire time of passed client: \n%s' % _sql)
        conn_iredapd.execute(_sql)

        return SMTP_ACTIONS['default']

    # check greylisting tracking.
    if _should_be_greylisted_by_tracking(conn=conn_iredapd,
                                         sender=sender,
                                         sender_domain=sender_domain,
                                         recipient=recipient,
                                         recipient_domain=recipient_domain,
                                         client_address=client_address):
        if settings.GREYLISTING_TRAINING_MODE:
            logger.debug("Running in greylisting training mode, bypass.")
        else:
            return action_greylisting

    return SMTP_ACTIONS['default']
