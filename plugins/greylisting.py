# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Greylisting.

# TODO Support per-domain whitelisting for greylisting service.

"""
* Please read tutorial below to understand how to manage greylisting settings:
  http://www.iredmail.org/docs/manage.iredapd.html

* Understand greylisting:
  http://projects.puremagic.com/greylisting/whitepaper.html
"""

import time
import ipaddress

from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS, ACCOUNT_PRIORITIES
from libs import utils, dnsspf
import settings  # pyright: ignore[reportMissingImports]

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import get_alias_target_domain
else:
    from libs.sql import get_alias_target_domain

# Return 4xx with greylisting message to Postfix.
action_greylisting = SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE


def _is_whitelisted(engine_iredapd,
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

    whitelists = set()

    for tbl in ['greylisting_whitelist_domain_spf', 'greylisting_whitelists']:
        # query whitelists based on recipient
        sql = """SELECT LOWER(sender)
                   FROM %s
                  WHERE account IN %s""" % (tbl, sqlquote(recipients))

        logger.debug('[SQL] Query greylisting whitelists from `{}`: \n{}'.format(tbl, sql))
        qr = utils.execute_sql(engine_iredapd, sql)
        records = qr.fetchall()

        _wls = {v[0] for v in records}

        # check whether sender (email/domain/ip) is explicitly whitelisted
        if client_address in _wls:
            logger.info('[%s] Client IP is explictly whitelisted for greylisting service.' % (client_address))
            return True

        _wl_senders = set(senders) & set(_wls)
        if _wl_senders:
            logger.info('[{}] Sender address is explictly whitelisted for greylisting service: {}'.format(client_address, ', '.join(_wl_senders)))
            return True

        whitelists.update(_wls)

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
                _net = ipaddress.ip_network(_cidr)
                if ip_object in _net:
                    logger.info('[{}] Client network is whitelisted: cidr={}'.format(client_address, _cidr))
                    return True
            except Exception as e:
                logger.debug('Not an valid IP network: sender={}, error={}'.format(_cidr, repr(e)))

    logger.debug('No whitelist found.')
    return False


def _client_address_passed_in_tracking(engine_iredapd, client_address):
    sql = """SELECT id
               FROM greylisting_tracking
              WHERE client_address=%s AND passed=1
              LIMIT 1""" % sqlquote(client_address)

    logger.debug('[SQL] check whether client address ({}) passed greylisting: \n{}'.format(client_address, sql))
    qr = utils.execute_sql(engine_iredapd, sql)
    sql_record = qr.fetchone()

    if sql_record:
        logger.debug('Client address (%s) passed greylisting.' % client_address)
        return True
    else:
        logger.debug("Client address (%s) didn't pass greylisting." % client_address)
        return False


def _should_be_greylisted_by_setting(engine_iredapd,
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

    qr = utils.execute_sql(engine_iredapd, sql)
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
                    except Exception as e:
                        logger.debug('Not a valid IP network: {} (error: {})'.format(_sender, e))

        if _matched:
            if _active == 1:
                logger.debug("Greylisting should be applied according to SQL "
                             "record: (id={}, account='{}', sender='{}')".format(_id, _account, _sender))
                return True
            else:
                logger.debug("Greylisting should NOT be applied according to "
                             "SQL record: (id={}, account='{}', sender='{}')".format(_id, _account, _sender))
                # return directly
                return False

    # No matched setting, turn off greylisting
    logger.debug('No matched setting, fallback to turn off greylisting.')
    return False


def _should_be_greylisted_by_tracking(engine_iredapd,
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
    sql_record = None
    try:
        qr = utils.execute_sql(engine_iredapd, sql)
        sql_record = qr.fetchone()
    except Exception as e:
        logger.error('Error while querying greylisting tracking: {}. SQL: {}'.format(repr(e), sql))

    if not sql_record:
        # Not record found, insert a new one.
        logger.info('[{}] Client has not been seen before, greylisted ({}).'.format(client_address, sender_domain))

        sender_domain = sqlquote(sender_domain)
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
            utils.execute_sql(engine_iredapd, sql)
        except Exception as e:
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
        utils.execute_sql(engine_iredapd, sql)
        return True

    # Tracking record doesn't expire, check whether client retries too soon.
    if now < _block_expired:
        # blocking not expired
        logger.info('[{}] Client retries too soon, greylisted again ({}).'.format(client_address, sender_domain))
        sql = """UPDATE greylisting_tracking
                    SET blocked_count=blocked_count + 1
                  WHERE     sender=%s
                        AND recipient=%s
                        AND client_address=%s""" % (sender, recipient, client_address_sql)

        logger.debug('[SQL] Update tracking record: \n%s' % sql)
        try:
            utils.execute_sql(engine_iredapd, sql)
        except Exception as e:
            logger.error('Error while updating greylisting tracking: %s' % repr(e))
            utils.execute_sql(engine_iredapd, sql)
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
                utils.execute_sql(engine_iredapd, sql)
            except Exception as e:
                logger.error('[{}] Error while Updating expired date for passed client: {}'.format(client_address, repr(e)))

            # Remove other tracking records from same client IP address to save
            # database space.
            sql = """DELETE FROM greylisting_tracking
                      WHERE client_address=%s AND passed=0""" % (client_address_sql)

            logger.debug('[SQL] Remove other tracking records from same client IP address: \n%s' % sql)
            try:
                utils.execute_sql(engine_iredapd, sql)
            except Exception as e:
                logger.error('[{}] Error while removing other tracking records from passed client: {}'.format(client_address, repr(e)))

        return False


def restriction(**kwargs):
    # Bypass outgoing emails.
    if kwargs['sasl_username']:
        logger.debug('Found SASL username, bypass greylisting for outbound email.')
        return SMTP_ACTIONS['default']

    client_address = kwargs['client_address']
    if utils.is_trusted_client(client_address):
        return SMTP_ACTIONS['default']

    sender = kwargs['sender_without_ext']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient_without_ext']
    recipient_domain = kwargs['recipient_domain']

    policy_recipients = utils.get_policy_addresses_from_email(mail=recipient)
    policy_senders = utils.get_policy_addresses_from_email(mail=sender)
    policy_senders += [client_address]

    # If recipient_domain is an alias domain name, we should check the target
    # domain.
    conn_vmail = kwargs['conn_vmail']
    alias_target_rcpt_domain = get_alias_target_domain(conn_vmail=conn_vmail, alias_domain=recipient_domain)
    if alias_target_rcpt_domain:
        _addr = recipient.split('@', 1)[0] + '@' + alias_target_rcpt_domain
        policy_recipients += utils.get_policy_addresses_from_email(mail=_addr)

    if utils.is_ipv4(client_address):
        # Add wildcard ip address: xx.xx.xx.*.
        policy_senders += client_address.rsplit('.', 1)[0] + '.*'

    # Get object of IP address type
    _ip_object = ipaddress.ip_address(client_address)

    engine_iredapd = kwargs['engine_iredapd']
    # Check greylisting whitelists
    if _is_whitelisted(engine_iredapd=engine_iredapd,
                       senders=policy_senders,
                       recipients=policy_recipients,
                       client_address=client_address,
                       ip_object=_ip_object):
        return SMTP_ACTIONS['default']

    # Check greylisting settings
    if not _should_be_greylisted_by_setting(engine_iredapd=engine_iredapd,
                                            recipients=policy_recipients,
                                            senders=policy_senders,
                                            client_address=client_address,
                                            ip_object=_ip_object):
        return SMTP_ACTIONS['default']

    # Bypass if sender server is listed in SPF DNS record of sender domain.
    if settings.GREYLISTING_BYPASS_SPF:
        if sender_domain == settings.srs_domain:
            # Don't check if sender domain (in smtp session) is same as SRS
            # domain. It's probably local server has SRS enabled, and Postfix
            # rewrites address before communicates with SMTP policy server (iRedAPD).
            pass
        elif dnsspf.is_allowed_server_in_spf(sender_domain=sender_domain, ip=client_address):
            logger.info('[{}] Bypass greylisting due to SPF match ({})'.format(client_address, sender_domain))
            return SMTP_ACTIONS['default']

    if _client_address_passed_in_tracking(engine_iredapd=engine_iredapd, client_address=client_address):
        # Update expire time
        _now = int(time.time())
        _new_expire_time = _now + settings.GREYLISTING_AUTH_TRIPLET_EXPIRE * 24 * 60 * 60
        _sql = """UPDATE greylisting_tracking
                     SET record_expired=%d
                   WHERE client_address=%s AND passed=1""" % (_new_expire_time, sqlquote(client_address))
        logger.debug('[SQL] Update expire time of passed client: \n%s' % _sql)
        utils.execute_sql(engine_iredapd, _sql)

        return SMTP_ACTIONS['default']

    # check greylisting tracking.
    if _should_be_greylisted_by_tracking(engine_iredapd=engine_iredapd,
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
