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
#    smtpd_recipient_restrictions =
#           ...
#           check_policy_service inet:[127.0.0.1]:7777
#           permit_mynetworks
#           ...
#
#    smtpd_end_of_data_restrictions =
#           check_policy_service inet:[127.0.0.1]:7777
#           ...
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py.
# *) Restart both iRedAPD and Postfix services.

# Technology details
# -------------
#
# Currently you may throttle based on amount of mails and total mail size
# sent over a given period of time, or size of singe message.
#
# Eg: You can enforce that user@domain.com does not send more than 1000 mails
# or 1GB of mail (whichever limit is hit first) in say a 5 minute period.
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
from web import sqlliteral, sqlquote
import settings
from libs import SMTP_ACTIONS
from libs.utils import is_ipv4, wildcard_ipv4, sqllist, is_trusted_client
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

    if is_ipv4(client_address):
        possible_addrs += wildcard_ipv4(client_address)

    throttle_type = 'sender'
    throttle_kind = 1       # throttle.kind
    if not is_sender_throttling:
        throttle_type = 'recipient'
        throttle_kind = 0

    logging.debug('Possible addresses:\n%s' % str(possible_addrs))

    sql = """
        SELECT id, account, priority, period, max_msgs, max_quota, msg_size
          FROM throttle
         WHERE kind=%d AND account IN %s
         ORDER BY priority DESC
         """ % (throttle_kind, sqllist(possible_addrs))

    logging.debug('[SQL] Query throttle setting:\n%s' % sql)
    qr = conn.execute(sql)
    throttle_records = qr.fetchall()

    logging.debug('[SQL] Query result:\n%s' % str(throttle_records))

    if not throttle_records:
        logging.debug('No %s throttle setting.' % throttle_type)
        return SMTP_ACTIONS['default']

    # construct the throttle setting
    t_setting = {}
    t_setting_keys = {}

    # Inherit throttle settings with lower priority.
    continue_check_msg_size = True
    continue_check_max_msgs = True
    continue_check_max_quota = True

    # print detailed throttle setting
    throttle_info = ''

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
                                     'track_key': [_account]}
            t_setting_keys[(_id, _account)] = 'msg_size'
            throttle_info += 'msg_size=%(value)d (bytes)/id=%(tid)d/account=%(account)s' % t_setting['msg_size']

        if continue_check_max_msgs and _max_msgs >= 0:
            continue_check_max_msgs = False
            t_setting['max_msgs'] = {'value': _max_msgs,
                                     'period': _period,
                                     'tid': _id,
                                     'account': _account,
                                     'track_key': [_account]}
            t_setting_keys[(_id, _account)] = 'max_msgs'
            throttle_info += 'max_msgs=%(value)d/id=%(tid)d/account=%(account)s; ' % t_setting['max_msgs']

        if continue_check_max_quota and _max_quota >= 0:
            continue_check_max_quota = False
            t_setting['max_quota'] = {'value': _max_quota,
                                      'period': _period,
                                      'tid': _id,
                                      'account': _account,
                                      'track_key': [_account]}
            t_setting_keys[(_id, _account)] = 'max_quota'
            throttle_info += 'max_quota=%(value)d (bytes)/id=%(tid)d/account=%(account)s; ' % t_setting['max_quota']

    if not t_setting:
        logging.debug('No valid %s throttle setting.' % throttle_type)
        return SMTP_ACTIONS['default']

    # If it's not per-user throttle (e.g. `@domain.com`), we should update both
    # per-user throttle tracking and original throttle tracking.
    #
    # (tid = tid AND account = track_key)
    sql_where = set()
    for (k, v) in t_setting.items():
        sql_where.add('(tid = %d AND account=%s)' % (v['tid'], sqlquote(v['account'])))

        if v['account'] != user:
            v['track_key'].append(user)
            t_setting[k] = v
            sql_where.add('(tid=%d AND account=%s)' % (v['tid'], sqlquote(user)))

    # Get throttle tracking data.
    # Construct SQL query WHERE statement
    sql = """
        SELECT id, tid, account, cur_msgs, cur_quota, init_time, last_time
          FROM throttle_tracking
         WHERE %s
         """ % ' OR '.join(sql_where)

    logging.debug('[SQL] Query throttle tracking data:\n%s' % sql)
    qr = conn.execute(sql)
    tracking_records = qr.fetchall()

    logging.debug('[SQL] Query result:\n%s' % str(tracking_records))

    for rcd in tracking_records:
        (_id, _tid, _account, _cur_msgs, _cur_quota, _init_time, _last_time) = rcd

        # Get special throttle setting name: msg_size, max_msgs, max_quota
        t_name = t_setting_keys.get((_tid, _account))
        if t_name in t_setting:
            #t_setting[t_name]['tracking_id'] = _id
            t_setting[t_name]['cur_msgs'] = _cur_msgs
            t_setting[t_name]['cur_quota'] = _cur_quota
            t_setting[t_name]['init_time'] = _init_time
            t_setting[t_name]['last_time'] = _last_time

    now = int(time.time())

    # Apply throttle setting on different protocol_state:
    #
    #   * RCPT: max_msgs
    #   * END-OF-MESSAGE: msg_size, max_quota

    # Note: Don't update `cur_msgs` in 'RCPT' state, because
    # current mail may be rejected by other plugins in 'END-OF-MESSAGE'
    # state or other restrictions in Postfix.

    if 'max_msgs' in t_setting:
        max_msgs = t_setting['max_msgs']['value']
        max_msgs_period = t_setting['max_msgs']['period']

        cur_msgs = t_setting['max_msgs'].get('cur_msgs', 0)
        max_msgs_init_time = t_setting['max_msgs'].get('init_time', 0)
        max_msgs_last_time = t_setting['max_msgs'].get('last_time', 0)

    # Check `max_msgs` in RCPT state
    if protocol_state == 'RCPT' and 'max_msgs' in t_setting:
        if now > (max_msgs_init_time + max_msgs_period):
            cur_msgs = 0

        if cur_msgs >= max_msgs > 0:
            logging.info('Exceeds %s throttle for max_msgs, current: %d. (%s)' % (throttle_type, cur_msgs, throttle_info))
            return SMTP_ACTIONS['reject_exceed_max_msgs']

    elif protocol_state == 'END-OF-MESSAGE':
        # SQL statements used to update tracking data if not rejected:
        # init_time, cur_msgs, cur_quota, last_time
        sql_update_sets = {}

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
            max_quota_period = t_setting['max_quota']['period']

            cur_quota = t_setting['max_quota'].get('cur_quota', 0)
            max_quota_init_time = t_setting['max_quota'].get('init_time', 0)
            max_quota_last_time = t_setting['max_quota'].get('last_time', 0)

            if now > (max_quota_init_time + max_quota_period):
                # tracking record expired
                cur_quota = 0

            if cur_quota > max_quota > 0:
                logging.info('Exceeds %s throttle for max_quota, current: %d. (%s)' % (throttle_type, cur_quota, throttle_info))
                return SMTP_ACTIONS['reject_exceed_max_quota']

        # Update or initialize tracking records.
        for (k, v) in t_setting.items():
            print k, v
        # initialize tracking records.
        #for (k, v) in t_setting.items():
        #    for acct in v['track_key']:
        #        sql = '''INSERT INTO throttle_tracking (tid, account, cur_msgs, cur_quota, init_time, last_time)
        #        VALUES (%d, %s, 1, 1, %d, %d, %d, %d)''' % (v['tid'], sqlquote(acct), size, size, now, now)
        #        conn.execute(sql)

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

    #if sender_domain == recipient_domain:
    #    logging.debug('Sender domain (@%s) is same as recipient domain, skip throttling.' % sender_domain)
    #    return SMTP_ACTIONS['default']

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
