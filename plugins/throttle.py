# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Throttle based on amount of mails and total mail size sent over
#          a given period of time, or size of single message.
#
# Note: To keep the database compact, you should set up a daily cron job to
#       clean up old/inactive records.

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

# Technical details
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
# Possible throttling address:
#
#   *) Full email address: user@domain.com
#   *) Domain name (with a prefixed '@'): @domain.com
#   *) Sub-domain name (with a prefixed '@.'): @.domain.com
#   *) IP address:  192.168.1.1
#   *) IP network:  192.168.1.*
#
# Priorities of different thorttle address (larger digital number has higher priority):
#
#   *) ip: 10,
#   *) email: 8,
#   *) wildcard_addr: 6,     # e.g. `user@*`. used in plugin `amavisd_wblist`
#                            # as wildcard sender. e.g. 'user@*`
#   *) domain: 5,
#   *) subdomain: 3,
#   *) top_level_domain: 1,
#   *) catchall: 0,

# ------------
# Valid settings:
#
#   * msg_size: max size of single message
#   * max_msgs: max number of sent messages
#   * max_quota: max number of accumulated message size
#
# Sample sender throttle settings:
#
# *) Allow user `user@domain.com` to send in 6 minutes (period_sent=360):
#
#   * max size of single message is 10240000 bytes (msg_size)
#   * max 100 messages (max_msgs)
#   * max 4096000000 bytes (max_quota)
#
#  INSERT INTO throttle_sender (user, priority, period, msg_size, max_msgs, max_quota)
#                       VALUES ('user@domain.com',
#                               10,
#                               360,
#                               10240000,
#                               100,
#                               4096000000);
#
# Sample recipient throttle settings:
#
# *) Allow user 'user@domain.com' to receive in 6 minutes (period=360):
#
#   * max size of single message is 10240000 bytes (msg_size)
#   * max 100 messages (max_msgs)
#   * max 4096000000 bytes (max_quota)
#
#  INSERT INTO throttle_rcpt (user, priority, period, msg_size, max_msgs, max_quota)
#                     VALUES ('user@domain.com',
#                             10,
#                             360,
#                             10240000,
#                             100,
#                             4096000000);
#
# ------------
# Possible value for throttle setting: msg_size, max_msgs, max_quota.
#
#  * XX (an integer number): explicit limit. e.g. 100. for example, set
#       `max_msgs=100` means user can send/receive up to 100 messages.
#  * 0:  unlimited.
#  * -1: inherit setting which has lower priority. for example, set
#       `msg_size=-1` for user `user@domain.com` will force iRedADP to check
#       `msg_size` setting in per-domain (`@domain.com`) and/or global (`@.`)
#       throttle settings.

import time
import logging
from web import sqlquote
import settings
from libs import SMTP_ACTIONS
from libs.utils import is_ipv4, wildcard_ipv4, sqllist, is_trusted_client
from libs.utils import is_valid_amavisd_address
from libs.amavisd.core import get_valid_addresses_from_email

SMTP_PROTOCOL_STATE = ['RCPT', 'END-OF-MESSAGE']

# Connect to iredapd database
REQUIRE_IREDAPD_DB = True


# Apply throttle setting and return smtp action.
def apply_throttle(conn,
                   user,
                   client_address,
                   protocol_state,
                   size,
                   is_sender_throttling=True):
    possible_addrs = get_valid_addresses_from_email(user)
    possible_addrs.append(client_address)

    sql_user = sqlquote(user)

    if is_ipv4(client_address):
        possible_addrs += wildcard_ipv4(client_address)

    throttle_type = 'sender'
    throttle_kind = 'outbound'       # throttle.kind
    if not is_sender_throttling:
        throttle_type = 'recipient'
        throttle_kind = 'inbound'

    logging.debug('Possible addresses:\n%s' % str(possible_addrs))

    sql = """
        SELECT id, account, priority, period, max_msgs, max_quota, msg_size
          FROM throttle
         WHERE kind=%s AND account IN %s
         ORDER BY priority DESC
         """ % (sqlquote(throttle_kind), sqllist(possible_addrs))

    logging.debug('[SQL] Query throttle setting:\n%s' % sql)
    qr = conn.execute(sql)
    throttle_records = qr.fetchall()

    logging.debug('[SQL] Query result:\n%s' % str(throttle_records))

    if not throttle_records:
        logging.debug('No %s throttle setting.' % throttle_type)
        return SMTP_ACTIONS['default']

    # Time of now. used for init_time and last_time.
    now = int(time.time())

    # construct the throttle setting
    t_setting = {}
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

        if continue_check_msg_size and _msg_size >= 0:
            continue_check_msg_size = False
            t_setting['msg_size'] = {'value': _msg_size,
                                     'period': _period,
                                     'tid': _id,
                                     'account': _account,
                                     'track_key': [],
                                     'expired': False,
                                     'cur_msgs': 0,
                                     'cur_quota': 0,
                                     'init_time': 0}
            t_setting_keys[(_id, _account)] = 'msg_size'
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'msg_size=%(value)d (bytes)/id=%(tid)d/account=%(account)s' % t_setting['msg_size']

        if continue_check_max_msgs and _max_msgs >= 0:
            continue_check_max_msgs = False
            t_setting['max_msgs'] = {'value': _max_msgs,
                                     'period': _period,
                                     'tid': _id,
                                     'account': _account,
                                     'track_key': [],
                                     'expired': False,
                                     'cur_msgs': 0,
                                     'cur_quota': 0,
                                     'init_time': 0}
            t_setting_keys[(_id, _account)] = 'max_msgs'
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'max_msgs=%(value)d/id=%(tid)d/account=%(account)s; ' % t_setting['max_msgs']

        if continue_check_max_quota and _max_quota >= 0:
            continue_check_max_quota = False
            t_setting['max_quota'] = {'value': _max_quota,
                                      'period': _period,
                                      'tid': _id,
                                      'account': _account,
                                      'track_key': [],
                                      'expired': False,
                                      'cur_msgs': 0,
                                      'cur_quota': 0,
                                      'init_time': 0}
            t_setting_keys[(_id, _account)] = 'max_quota'
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'max_quota=%(value)d (bytes)/id=%(tid)d/account=%(account)s; ' % t_setting['max_quota']

    if not t_setting:
        logging.debug('No valid %s throttle setting.' % throttle_type)
        return SMTP_ACTIONS['default']

    # Update track_key.
    for (t_name, v) in t_setting:
        t_account = v['account']
        addr_type = is_valid_amavisd_address(t_account)

        if addr_type in ['ip', 'wildcard_ip', 'wildcard_addr']:
            # Track based on IP, wildcard IP, wildcard address
            v['track_key'].append(t_account)
        else:
            v['track_key'].append(user)

    # Get throttle tracking data.
    # Construct SQL query WHERE statement
    sql = """
        SELECT id, tid, account, cur_msgs, cur_quota, init_time, last_time
          FROM throttle_tracking
         WHERE %s
         """ % ' OR '.join(tracking_sql_where)

    logging.debug('[SQL] Query throttle tracking data:\n%s' % sql)
    qr = conn.execute(sql)
    tracking_records = qr.fetchall()

    logging.debug('[SQL] Query result:\n%s' % str(tracking_records))

    # `throttle.id`. syntax: {(tid, account): id}
    tracking_ids = {}

    for rcd in tracking_records:
        (_id, _tid, _account, _cur_msgs, _cur_quota, _init_time, _last_time) = rcd

        tracking_ids[(_tid, _account)] = _id

        if not _init_time:
            _init_time = now

        # Get special throttle setting name: msg_size, max_msgs, max_quota
        t_name = t_setting_keys.get((_tid, _account))
        if t_name in t_setting:
            t_setting[t_name]['cur_msgs'] = _cur_msgs
            t_setting[t_name]['cur_quota'] = _cur_quota
            t_setting[t_name]['init_time'] = _init_time
            t_setting[t_name]['last_time'] = _last_time

    # Apply throttle setting on different protocol_state:
    #
    #   * RCPT: max_msgs
    #   * END-OF-MESSAGE: msg_size, max_quota

    # Reset `init_time` for `max_msgs`.
    if 'max_msgs' in t_setting:
        max_msgs_period = t_setting['max_msgs']['period']
        max_msgs_init_time = t_setting['max_msgs']['init_time']
        max_msgs_cur_msgs = t_setting['max_msgs']['cur_msgs']

        if max_msgs_period and now > (max_msgs_init_time + max_msgs_period):
            t_setting['max_msgs']['expired'] = True
            max_msgs_cur_msgs = 0

    # Check `max_msgs` in RCPT state
    #
    # Note: Don't update any tracking data in 'RCPT' state, because
    # current mail may be rejected by other plugins in 'END-OF-MESSAGE'
    # state or other restrictions in Postfix.
    if protocol_state == 'RCPT' and 'max_msgs' in t_setting:
        max_msgs = t_setting['max_msgs']['value']

        if max_msgs_cur_msgs >= max_msgs > 0:
            logging.info('Exceeds %s throttle for max_msgs, current: %d. (%s)' % (throttle_type, max_msgs_cur_msgs, throttle_info))
            return SMTP_ACTIONS['reject_exceed_max_msgs']

    elif protocol_state == 'END-OF-MESSAGE':
        # Check `msg_size`
        if 'msg_size' in t_setting:
            msg_size = t_setting['msg_size']['value']

            # Check message size
            if size > msg_size > 0:
                logging.info('Exceeds %s throttle for msg_size, current: %d (bytes). (%s)' % (throttle_type, size, throttle_info))
                return SMTP_ACTIONS['reject_exceed_msg_size']

        # Check `max_quota`
        if 'max_quota' in t_setting:
            max_quota = t_setting['max_quota']['value']
            period = t_setting['max_quota']['period']

            cur_quota = t_setting['max_quota']['cur_quota']
            init_time = t_setting['max_quota']['init_time']

            if period and now > (init_time + period):
                # tracking record expired
                t_setting['max_quota']['expired'] = True
                cur_quota = 0

            if cur_quota > max_quota > 0:
                logging.info('Exceeds %s throttle for max_quota, current: %d. (%s)' % (throttle_type, cur_quota, throttle_info))
                return SMTP_ACTIONS['reject_exceed_max_quota']

        # Update tracking record.
        #
        # SQL statements used to update tracking data if not rejected:
        # init_time, cur_msgs, cur_quota, last_time
        sql_inserts = []
        sql_update_sets = {}

        for t_name in t_setting:
            tid = t_setting[t_name]['tid']
            for k in t_setting[t_name]['track_key']:
                if (tid, k) in tracking_ids:
                    # Update existing tracking records
                    tracking_id = tracking_ids[(tid, k)]

                    if not tracking_id in sql_update_sets:
                        sql_update_sets[tracking_id] = []

                    _sql = []
                    _sql += ['last_time = %d' % now]

                    if t_setting[t_name]['expired']:
                        _sql += ['init_time = %d' % now]
                        _sql += ['cur_msgs = 1']
                        _sql += ['cur_quota = %d' % size]
                    else:
                        _sql += ['init_time = %d' % t_setting[t_name]['init_time']]
                        _sql += ['cur_msgs = cur_msgs + 1']
                        _sql += ['cur_quota = cur_quota + %d' % size]

                    sql_update_sets[tracking_id] = _sql

                else:
                    # no tracking record. insert new one.
                    # (tid, account, cur_msgs, cur_quota, init_time, last_time)
                    if not (tid, k) in sql_inserts:
                        _sql = '(%d, %s, 1, %d, %d, %d)' % (tid, sqlquote(k), size, now, now)

                        sql_inserts.append(_sql)

        if sql_inserts:
            sql = """INSERT INTO throttle_tracking
                                 (tid, account, cur_msgs, cur_quota, init_time, last_time)
                          VALUES """
            sql += ','.join(set(sql_inserts))

            logging.debug('[SQL] Insert new tracking record(s):\n%s' % sql)
            conn.execute(sql)

        if sql_update_sets:
            sql = ''
            for (k, v) in sql_update_sets.items():
                _sql = """
                    UPDATE throttle_tracking
                       SET %s
                     WHERE id=%d;
                     """ % (','.join(v), k)
                sql += _sql

            logging.debug('[SQL] Update tracking record(s):\n%s' % sql)
            conn.execute(sql)

    logging.debug('[OK] Passed all %s throttle settings.' % throttle_type)
    return SMTP_ACTIONS['default']


def restriction(**kwargs):
    conn = kwargs['conn_iredapd']

    # Use SASL username as sender. if not available, use sender in 'From:'.
    sender = kwargs['sasl_username'] or kwargs['sender']
    sender_domain = kwargs['sasl_username_domain'] or kwargs['sender_domain']

    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']
    client_address = kwargs['client_address']
    protocol_state = kwargs['smtp_session_data']['protocol_state']
    size = kwargs['smtp_session_data']['size']
    if size:
        size = int(size)
    else:
        size = 0

    if sender_domain == recipient_domain:
        logging.debug('Sender domain (@%s) is same as recipient domain, skip throttling.' % sender_domain)
        return SMTP_ACTIONS['default']

    if settings.THROTTLE_BYPASS_MYNETWORKS:
        if is_trusted_client(client_address):
            return SMTP_ACTIONS['default']

    logging.debug('Check sender throttling.')
    action = apply_throttle(conn=conn,
                            user=sender,
                            client_address=client_address,
                            protocol_state=protocol_state,
                            size=size,
                            is_sender_throttling=True)

    if not action.startswith('DUNNO'):
        return action

    logging.debug('Check recipient throttling.')
    action = apply_throttle(conn=conn,
                            user=recipient,
                            client_address=client_address,
                            protocol_state=protocol_state,
                            size=size,
                            is_sender_throttling=False)

    if not action.startswith('DUNNO'):
        return action

    return SMTP_ACTIONS['default']
