# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Throttle based on amount of mails and total mail size sent over
#          a given period of time, or size of single message.
#
# Note: To keep the database compact, you should set up a daily cron job with
#       'tools/cleanup_db.py' to clean up expired throttle tracking records.

# Usage
# -------------
#
# *) Enable iRedAPD in Postfix parameters: `smtpd_recipient_restrictions` and
#    `smtpd_end_of_data_restrictions`. For example:
#
#    # Check max_msgs
#    smtpd_recipient_restrictions =
#           ...
#           check_policy_service inet:[127.0.0.1]:7777
#           permit_mynetworks
#           ...
#
#    # Check msg_size and max_quota
#    smtpd_end_of_data_restrictions =
#           check_policy_service inet:[127.0.0.1]:7777
#           ...
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py.
# *) Restart both iRedAPD and Postfix services.

# Technical details of Postfix policy
# -------------
#
# if email has multiple recipients:
#
#   *) Postfix send policy request at RCPT state for each recipient. Policy
#      server knows the recipient address, but not `recipient_count`.
#
#   *) Postfix send ONLY ONE policy request at END-OF-MESSAGE state. Policy
#      server doesn't know the recipient address, but knows `recipient_count`.
#
#   *) If some recipients were rejected at RCPT state, Postfix will correctly
#      store the number of final recipients in `recipient_count`.

# Technical details of throttle plugin
# -------------
#
# Currently you may throttle based on:
#
#   - amount of mails sent over a given period of time
#   - accumulated mail size sent over a given period of time
#   - size of singe message
#
# Eg: You can enforce that user@domain.com does not send more than 1000 mails
# or 1GB of mail (whichever limit is hit first) in 5 minute.
#
# Valid throttling address format:
#
#   *) Full email address: user@domain.com
#   *) Domain name (with a prefixed '@'): @domain.com
#   *) Sub-domain name (with a prefixed '@.'): @.domain.com
#   *) IP address:  192.168.1.1
#   *) IP network:  192.168.1.*
#   *) Catch-all for email address: '@.' (note, the dot is required)
#   *) Catch-all for IP address: '@ip' (applies to per ip address)
#
# Priorities of different thorttle address (larger digital number has higher priority):
#
#   *) email: 100           # e.g. 'user@domain.com'. Highest priority
#   *) wildcard_addr: 90    # e.g. `user@*`. used in plugin `amavisd_wblist`
#                           # as wildcard sender. e.g. 'user@*`
#   *) ip: 80               # e.g. 173.254.22.21
#   *) wildcard_ip: 70      # e.g. 173.254.22.*
#   *) cidr: 70             # e.g. 173.254.22.0/24
#   *) domain: 60           # e.g. @domain.com
#   *) subdomain: 50        # e.g. @.domain.com
#   *) top_level_domain: 40 # e.g. @com, @org
#   *) catchall: 0          # '@.'. Lowest priority

# ------------
# Valid throttle settings:
#
#   * msg_size: max size of single message
#   * max_msgs: max number of sent messages
#   * max_quota: max number of accumulated message size
#
# Valid values for throttle settings:
#
#  * XX (an integer number): explicit limit. e.g. 100. for example, set
#       `max_msgs=100` means user can send/receive up to 100 messages.
#  * 0: (explicit) unlimited.
#  * -1: inherit setting which has lower priority. for example, set
#       `msg_size=-1` for user `user@domain.com` will force iRedADP to check
#       `msg_size` setting in per-domain (`@domain.com`) and/or global (`@.`)
#       throttle settings.
#

# -------------
# Different throttle types (SQL column `throttle.kind`):
#
#   - inbound: email sent from other mail servers.
#   - outbound: emails sent by authenticated users.
#   - external: emails sent from other mail servers.
#
# Difference between `inbound` and `external`:
#   - `inbound` is set based on sender addresses which are your local users.
#   - `external` is set based on sender addresses which are NOT your local users.

####################################
# Sample sender throttle settings:
#
# *) Allow local user `user@domain.com` to send in 6 minutes (period=360):
#
#   * value of sql column `throttle.kind` is 'outbound'
#   * max size of single message is 10240000 bytes (msg_size)
#   * max 100 messages (max_msgs)
#   * max 4096000000 bytes (max_quota)
#
#  INSERT INTO throttle (account, kind, priority, period, msg_size, max_msgs, max_quota)
#                VALUES ('user@domain.com',
#                        'outbound',
#                        10,
#                        360,
#                        10240000,
#                        100,
#                        4096000000);
#
# *) Allow external user `user@not-my-domain.com` to send in 6 minutes (period=360):
#
#   * value of sql column `throttle.kind` is 'external'
#
#  INSERT INTO throttle (account, kind, priority, period, msg_size, max_msgs, max_quota)
#                VALUES ('user@not-my-domain.com',
#                        'external',
#                        10,
#                        360,
#                        10240000,
#                        100,
#                        4096000000);
#
#####################################
# Sample recipient throttle settings:
#
# *) Allow local user 'user@domain.com' to receive in 6 minutes (period=360):
#
#   * value of sql column `throttle.kind` is 'inbound'
#   * max size of single message is 10240000 bytes (msg_size)
#   * max 100 messages (max_msgs)
#   * max 4096000000 bytes (max_quota)
#
#  INSERT INTO throttle (account, kind, priority, period, msg_size, max_msgs, max_quota)
#                VALUES ('user@domain.com',
#                        'inbound',
#                        10,
#                        360,
#                        10240000,
#                        100,
#                        4096000000);

import time
from libs.logger import logger
from web import sqlquote
import settings
from libs import SMTP_ACTIONS
from libs.utils import is_ipv4, wildcard_ipv4, is_trusted_client, get_policy_addresses_from_email
from libs.utils import is_valid_amavisd_address, pretty_left_seconds

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import get_alias_target_domain
else:
    from libs.sql import get_alias_target_domain

SMTP_PROTOCOL_STATE = ['RCPT', 'END-OF-MESSAGE']

# Connect to iredapd database
REQUIRE_IREDAPD_DB = True


# Apply throttle setting and return smtp action.
def apply_throttle(conn,
                   conn_vmail,
                   user,
                   client_address,
                   protocol_state,
                   size,
                   recipient_count,
                   instance_id,
                   is_sender_throttling=True,
                   is_external_sender=False):
    possible_addrs = [client_address, '@ip']

    if user:
        possible_addrs += get_policy_addresses_from_email(mail=user)

        (_username, _domain) = user.split('@', 1)
        alias_target_sender_domain = get_alias_target_domain(alias_domain=_domain, conn=conn_vmail)
        if alias_target_sender_domain:
            _mail = _username + '@' + alias_target_sender_domain
            possible_addrs += get_policy_addresses_from_email(mail=_mail)

    sql_user = sqlquote(user)

    if is_ipv4(client_address):
        possible_addrs += wildcard_ipv4(client_address)

    if is_sender_throttling:
        throttle_type = 'sender'
        throttle_kind = 'outbound'

        if is_external_sender:
            throttle_kind = 'external'
    else:
        throttle_type = 'recipient'
        throttle_kind = 'inbound'

    sql = """
        SELECT id, account, priority, period, max_msgs, max_quota, msg_size
          FROM throttle
         WHERE kind=%s AND account IN %s
         ORDER BY priority DESC
         """ % (sqlquote(throttle_kind), sqlquote(possible_addrs))

    logger.debug('[SQL] Query throttle setting:\n%s' % sql)
    qr = conn.execute(sql)
    throttle_records = qr.fetchall()

    logger.debug('[SQL] Query result:\n%s' % str(throttle_records))

    if not throttle_records:
        logger.debug('No %s throttle setting.' % throttle_type)
        return SMTP_ACTIONS['default']

    # Time of now. used for init_time and last_time.
    now = int(time.time())

    # construct the throttle setting
    t_settings = {}
    t_setting_ids = {}
    t_setting_keys = {}

    # Inherit throttle settings with lower priority.
    continue_check_msg_size = True
    continue_check_max_msgs = True
    continue_check_max_quota = True

    # print detailed throttle setting
    throttle_info = ''

    # sql where statements used to track throttle.
    # (tid = tid AND account = `user`)
    tracking_sql_where = set()

    for rcd in throttle_records:
        (_id, _account, _priority, _period, _max_msgs, _max_quota, _msg_size) = rcd

        # Skip throttle setting which doesn't have period
        if not _period:
            continue

        t_setting_keys[(_id, _account)] = []
        t_setting_ids[_id] = _account

        tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sqlquote(client_address)))

        if continue_check_msg_size and _msg_size == 0:
            continue_check_msg_size = False
            t_settings['msg_size'] = {'value': _msg_size,
                                      'period': _period,
                                      'tid': _id,
                                      'account': _account,
                                      'track_key': [],
                                      'expired': False,
                                      'cur_msgs': 0,
                                      'cur_quota': 0,
                                      'init_time': 0}
            t_setting_keys[(_id, _account)].append('msg_size')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'msg_size=%(value)d (bytes)/id=%(tid)d/account=%(account)s; ' % t_settings['msg_size']

        if continue_check_max_msgs and _max_msgs == 0:
            continue_check_max_msgs = False
            t_settings['max_msgs'] = {'value': _max_msgs,
                                      'period': _period,
                                      'tid': _id,
                                      'account': _account,
                                      'track_key': [],
                                      'expired': False,
                                      'cur_msgs': 0,
                                      'cur_quota': 0,
                                      'init_time': 0}
            t_setting_keys[(_id, _account)].append('max_msgs')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'max_msgs=%(value)d/id=%(tid)d/account=%(account)s; ' % t_settings['max_msgs']

        if continue_check_max_quota and _max_quota == 0:
            continue_check_max_quota = False
            t_settings['max_quota'] = {'value': _max_quota,
                                       'period': _period,
                                       'tid': _id,
                                       'account': _account,
                                       'track_key': [],
                                       'expired': False,
                                       'cur_msgs': 0,
                                       'cur_quota': 0,
                                       'init_time': 0}
            t_setting_keys[(_id, _account)].append('max_quota')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'max_quota=%(value)d (bytes)/id=%(tid)d/account=%(account)s; ' % t_settings['max_quota']

    if not t_settings:
        logger.debug('No valid %s throttle setting.' % throttle_type)
        return SMTP_ACTIONS['default']
    else:
        logger.debug('%s throttle setting: %s' % (throttle_type, throttle_info))

    # Update track_key.
    for (_, v) in t_settings.items():
        t_account = v['account']
        addr_type = is_valid_amavisd_address(t_account)

        if addr_type in ['ip', 'catchall_ip']:
            # Track based on IP address
            v['track_key'].append(client_address)
        elif addr_type in ['wildcard_ip', 'wildcard_addr']:
            # Track based on wildcard IP or sender address
            v['track_key'].append(t_account)
        else:
            # Track based on sender email address
            v['track_key'].append(user)

    # Get throttle tracking data.
    # Construct SQL query WHERE statement
    sql = """SELECT id, tid, account, cur_msgs, cur_quota, init_time, last_time
               FROM throttle_tracking
              WHERE %s
              """ % ' OR '.join(tracking_sql_where)

    logger.debug('[SQL] Query throttle tracking data:\n%s' % sql)
    qr = conn.execute(sql)
    tracking_records = qr.fetchall()

    logger.debug('[SQL] Query result:\n%s' % str(tracking_records))

    # `throttle.id`. syntax: {(tid, account): id}
    tracking_ids = {}

    for rcd in tracking_records:
        (_id, _tid, _account, _cur_msgs, _cur_quota, _init_time, _last_time) = rcd

        tracking_ids[(_tid, _account)] = _id

        if not _init_time:
            _init_time = now

        # Get special throttle setting name: msg_size, max_msgs, max_quota
        t_setting_account = t_setting_ids[_tid]
        for t_name in t_setting_keys.get((_tid, t_setting_account)):
            if t_name in t_settings:
                t_settings[t_name]['cur_msgs'] = _cur_msgs
                t_settings[t_name]['cur_quota'] = _cur_quota
                t_settings[t_name]['init_time'] = _init_time
                t_settings[t_name]['last_time'] = _last_time

    logger.debug('Tracking IDs: %s' % str(tracking_ids))

    # Apply throttle setting on different protocol_state:
    #
    #   * RCPT: max_msgs
    #   * END-OF-MESSAGE: msg_size, max_quota

    # Reset `init_time` for `max_msgs`.
    if 'max_msgs' in t_settings:
        max_msgs_period = t_settings['max_msgs']['period']
        max_msgs_init_time = t_settings['max_msgs']['init_time']
        max_msgs_cur_msgs = t_settings['max_msgs']['cur_msgs']

        if max_msgs_period and now > (max_msgs_init_time + max_msgs_period):
            logger.debug('Period of max_msgs expired, reset.')
            t_settings['max_msgs']['expired'] = True
            max_msgs_cur_msgs = 0

    # Check `max_msgs` in RCPT state
    #
    # Note: Don't update any tracking data in 'RCPT' state, because
    # current mail may be rejected by other plugins in 'END-OF-MESSAGE'
    # state or other restrictions in Postfix.
    if protocol_state == 'RCPT':
        if 'max_msgs' in t_settings:
            max_msgs = t_settings['max_msgs']['value']

            _period = int(t_settings['max_msgs'].get('period', 0))
            _init_time = int(t_settings['max_msgs'].get('init_time', 0))
            _last_time = int(t_settings['max_msgs'].get('last_time', 0))

            # Get the real cur_msgs (if mail contains multiple recipients, we
            # need to count them all)
            _real_max_msgs_cur_msgs = max_msgs_cur_msgs + settings.GLOBAL_SESSION_TRACKING[instance_id]['processed']

            if _real_max_msgs_cur_msgs >= max_msgs > 0:
                logger.info('[%s] [%s] Quota exceeded: %s throttle for max_msgs, current: %d. (%s)' % (
                    client_address,
                    user,
                    throttle_type,
                    max_msgs_cur_msgs,
                    throttle_info))

                return SMTP_ACTIONS['reject_quota_exceeded']
            else:
                # Show the time tracking record is about to expire
                _left_seconds = _init_time + _period - _last_time

                logger.info('[%s] %s throttle, %s -> max_msgs (%d/%d, period: %d seconds, %s)' % (
                    client_address,
                    throttle_type,
                    user,
                    max_msgs_cur_msgs,
                    max_msgs,
                    _period,
                    pretty_left_seconds(_left_seconds)))

    elif protocol_state == 'END-OF-MESSAGE':
        # Check `msg_size`
        if 'msg_size' in t_settings:
            msg_size = t_settings['msg_size']['value']

            _period = int(t_settings['msg_size'].get('period', 0))
            _init_time = int(t_settings['msg_size'].get('init_time', 0))
            _last_time = int(t_settings['msg_size'].get('last_time', 0))

            # Check message size
            if size > msg_size > 0:
                logger.info('[%s] [%s] Quota exceeded: %s throttle for msg_size, current: %d (bytes). (%s)' % (
                    client_address,
                    user,
                    throttle_type,
                    size,
                    throttle_info))

                return SMTP_ACTIONS['reject_quota_exceeded']
            else:
                # Show the time tracking record is about to expire
                _left_seconds = _init_time + _period - _last_time

                logger.info('[%s] %s throttle, %s -> msg_size (%d/%d, period: %d seconds, %s)' % (
                    client_address,
                    throttle_type,
                    user,
                    size,
                    msg_size,
                    _period,
                    pretty_left_seconds(_left_seconds)))

        # Check `max_quota`
        if 'max_quota' in t_settings:
            max_quota = t_settings['max_quota']['value']
            _cur_quota = t_settings['max_quota'].get('cur_quota', 0)

            _period = int(t_settings['msg_size'].get('period', 0))
            _init_time = int(t_settings['msg_size'].get('init_time', 0))
            _last_time = int(t_settings['msg_size'].get('last_time', 0))

            if _period and now > (_init_time + _period):
                # tracking record expired
                logger.debug('Period of max_quota expired, reset.')
                t_settings['max_quota']['expired'] = True
                _cur_quota = 0

            if _cur_quota > max_quota > 0:
                logger.info('[%s] [%s] Quota exceeded: %s throttle for max_quota, current: %d. (%s)' % (
                    client_address,
                    user,
                    throttle_type,
                    _cur_quota,
                    throttle_info))

                return SMTP_ACTIONS['reject_quota_exceeded']
            else:
                # Show the time tracking record is about to expire
                _left_seconds = _init_time + _period - _last_time

                logger.info('[%s] %s throttle, %s -> max_quota (%d/%d, period: %d seconds, %s)' % (
                    client_address,
                    throttle_type,
                    user,
                    _cur_quota,
                    max_quota,
                    _period,
                    pretty_left_seconds(_left_seconds)))

        # Update tracking record.
        #
        # SQL statements used to update tracking data if not rejected:
        # init_time, cur_msgs, cur_quota, last_time
        sql_inserts = []
        # {tracking_id: ['last_time=xxx', 'init_time=xxx', ...]}
        sql_updates = {}

        for (_, v) in t_settings.items():
            tid = v['tid']
            for k in v['track_key']:
                if (tid, k) in tracking_ids:
                    # Update existing tracking records
                    tracking_id = tracking_ids[(tid, k)]

                    if not (tracking_id in sql_updates):
                        sql_updates[tracking_id] = []

                    _sql = []

                    # Store period, used while cleaning up old tracking records.
                    _sql += ['period = %d' % v['period']]

                    _sql += ['last_time = %d' % now]

                    if v['expired']:
                        _sql += ['init_time = %d' % now]
                        _sql += ['cur_msgs = %d' % recipient_count]
                        _sql += ['cur_quota = %d' % size]
                    else:
                        _sql += ['init_time = %d' % v['init_time']]
                        _sql += ['cur_msgs = cur_msgs + %d' % recipient_count]
                        _sql += ['cur_quota = cur_quota + %d' % size]

                    sql_updates[tracking_id] = _sql

                else:
                    # no tracking record. insert new one.
                    # (tid, account, cur_msgs, period, cur_quota, init_time, last_time)
                    if not (tid, k) in sql_inserts:
                        _sql = '(%d, %s, %d, %d, %d, %d, %d)' % (tid, sqlquote(k), recipient_count, v['period'], size, now, now)

                        sql_inserts.append(_sql)

        if sql_inserts:
            sql = """INSERT INTO throttle_tracking
                                 (tid, account, cur_msgs, period, cur_quota, init_time, last_time)
                          VALUES """
            sql += ','.join(set(sql_inserts))

            logger.debug('[SQL] Insert new tracking record(s):\n%s' % sql)
            conn.execute(sql)

        if sql_updates:
            sql = ''
            for (k, v) in sql_updates.items():
                _sql = """
                    UPDATE throttle_tracking
                       SET %s
                     WHERE id=%d;
                     """ % (','.join(v), k)
                sql += _sql

            logger.debug('[SQL] Update tracking record(s):\n%s' % sql)
            conn.execute(sql)

    logger.debug('[OK] Passed all %s throttle settings.' % throttle_type)
    return SMTP_ACTIONS['default']


def restriction(**kwargs):
    conn = kwargs['conn_iredapd']
    conn_vmail = kwargs['conn_vmail']

    # Use SASL username as sender. if not available, use sender in 'From:'.
    sender = kwargs['sasl_username'] or kwargs['sender_without_ext']
    sender_domain = kwargs['sasl_username_domain'] or kwargs['sender_domain']

    recipient = kwargs['recipient_without_ext']
    recipient_domain = kwargs['recipient_domain']
    client_address = kwargs['client_address']

    smtp_session_data = kwargs['smtp_session_data']
    protocol_state = smtp_session_data['protocol_state']
    size = smtp_session_data['size']
    recipient_count = int(smtp_session_data['recipient_count'])
    instance_id = smtp_session_data['instance']

    if size:
        size = int(size)
    else:
        size = 0

    if sender_domain == recipient_domain and settings.THROTTLE_BYPASS_SAME_DOMAIN:
        logger.debug('SKIP: sender and recipient are under same domain (@%s), it is set to be bypassed.' % sender_domain)
        return SMTP_ACTIONS['default']

    if settings.THROTTLE_BYPASS_MYNETWORKS:
        if is_trusted_client(client_address):
            return SMTP_ACTIONS['default']

    # If no smtp auth (sasl_username=<empty>), and not sent from trusted
    # clients, consider it as external sender.
    is_external_sender = True
    if kwargs['sasl_username']:
        logger.debug('Found sasl_username, consider this sender as an internal sender.')
        is_external_sender = False
    else:
        if not settings.THROTTLE_BYPASS_MYNETWORKS:
            if is_trusted_client(client_address):
                logger.debug('Client is sending from trusted network without SMTP AUTH, consider this sender as an internal sender.')
                is_external_sender = False

    # Apply sender throttling to only sasl auth users.
    logger.debug('Check sender throttling.')
    action = apply_throttle(conn=conn,
                            conn_vmail=conn_vmail,
                            user=sender,
                            client_address=client_address,
                            protocol_state=protocol_state,
                            size=size,
                            recipient_count=recipient_count,
                            instance_id=instance_id,
                            is_sender_throttling=True,
                            is_external_sender=is_external_sender)

    if not action.startswith('DUNNO'):
        return action

    # Apply recipient throttling to smtp sessions without sasl_username
    if kwargs['sasl_username'] and settings.THROTTLE_BYPASS_LOCAL_RECIPIENT:
        # Both sender and recipient are local.
        logger.debug('Bypass recipient throttling (found sasl_username).')
    else:
        logger.debug('Check recipient throttling.')
        action = apply_throttle(conn=conn,
                                conn_vmail=conn_vmail,
                                user=recipient,
                                client_address=client_address,
                                protocol_state=protocol_state,
                                size=size,
                                recipient_count=recipient_count,
                                instance_id=instance_id,
                                is_sender_throttling=False)

        if not action.startswith('DUNNO'):
            return action

    return SMTP_ACTIONS['default']
