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
#    # Check msg_size, max_quota and max_rcpts.
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
#   *) Postfix sends policy request at RCPT state for each recipient, this
#      means iRedAPD gets only __ONE__ recipient address in RCPT state.
#
#   *) Postfix sends only __ONE__ policy request at END-OF-MESSAGE state. In
#      this state, iRedAPD doesn't get any recipient address, but gets a number
#      of recipient count (`recipient_count=`).
#
#   *) If some recipients are rejected at RCPT state, Postfix will correctly
#      store the count of final recipients in `recipient_count`.

# Technical details of throttle plugin
# -------------
#
# Currently you can throttle based on:
#
#   - amount of mails sent over a given period of time
#   - accumulated mail size sent over a given period of time
#   - size of singe message
#   - number of recipietns in single message
#
# For example, you can enforce that user `user@domain.com` is not able to send
# more than 1000 mails and / or 1GB of mail in 5 minutes, the first reached
# limit wins.
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
#   * max_rcpts: max recipients in single message
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
#   * max 12 recipients in one single message (max_rcpts)
#
#  INSERT INTO throttle (account, kind, priority, period, msg_size, max_msgs, max_quota, max_rcpts)
#                VALUES ('user@domain.com',
#                        'outbound',
#                        10,
#                        360,
#                        10240000,
#                        100,
#                        4096000000,
#                        12);
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
from web import sqlquote
from libs.logger import logger
import settings
from libs import SMTP_ACTIONS, utils

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import get_alias_target_domain
else:
    from libs.sql import get_alias_target_domain

SMTP_PROTOCOL_STATE = ['END-OF-MESSAGE']

# Connect to iredapd database
REQUIRE_IREDAPD_DB = True


def __sendmail(conn,
               user,
               client_address,
               throttle_tracking_id,
               throttle_name,
               throttle_value,
               throttle_kind,
               throttle_info,
               throttle_value_unit=None):
    """Construct and send notification email."""
    # conn: SQL connection cursor
    # user: user email address
    # client_address: client IP address
    # throttle_tracking_id: value of sql column `throttle_tracking.id`
    # throttle_name: name of throttle settings: msg_size, max_quota, max_msgs
    # throttle_value: value throttle setting
    # throttle_kind: one of throttle kinds: inbound, outbound
    # throttle_info: detailed throttle setting
    # throttle_value_unit: unit of throttle setting. e.g 'bytes' for max_quota
    #                      and msg_size.
    if not throttle_value_unit:
        throttle_value_unit = ''

    try:
        _subject = 'Throttle quota exceeded: %s, %s=%d %s' % (user, throttle_name, throttle_value, throttle_value_unit)
        _body = '- User: ' + user + '\n'
        _body += '- Client IP address: ' + client_address + '\n'
        _body += '- Throttle type: ' + throttle_kind + '\n'
        _body += '- Throttle setting: ' + throttle_name + '\n'
        _body += '- Limit: %d %s\n' % (throttle_value, throttle_value_unit)
        _body += '- Detailed setting: ' + throttle_info + '\n'

        utils.sendmail(subject=_subject, mail_body=_body)
        logger.info('Sent notification email to admin(s) to report quota exceed: user=%s, %s=%d.' % (user, throttle_name, throttle_value))

        if throttle_tracking_id:
            _now = int(time.time())

            # Update last_notify_time.
            _sql = """UPDATE throttle_tracking
                         SET last_notify_time=%d
                       WHERE id=%d;
                       """ % (_now, throttle_tracking_id)

            try:
                conn.execute(_sql)
                logger.debug('Updated last notify time.')
            except Exception as e:
                logger.error('Error while updating last notify time of quota exceed: %s.' % (repr(e)))

        return True,
    except Exception as e:
        logger.error('Error while sending notification email: %s' % repr(e))
        return False, repr(e)


# Apply throttle setting and return smtp action.
def apply_throttle(conn,
                   conn_vmail,
                   user,
                   client_address,
                   size,
                   recipient_count,
                   is_sender_throttling=True,
                   is_external_sender=False):
    possible_addrs = [client_address, '@ip']

    if user:
        possible_addrs += utils.get_policy_addresses_from_email(mail=user)

        (_username, _domain) = user.split('@', 1)
        alias_target_sender_domain = get_alias_target_domain(alias_domain=_domain, conn=conn_vmail)
        if alias_target_sender_domain:
            _mail = _username + '@' + alias_target_sender_domain
            possible_addrs += utils.get_policy_addresses_from_email(mail=_mail)

    sql_user = sqlquote(user)

    if utils.is_ipv4(client_address):
        possible_addrs += utils.wildcard_ipv4(client_address)

    if is_sender_throttling:
        throttle_type = 'sender'
        throttle_kind = 'outbound'

        if is_external_sender:
            throttle_kind = 'external'
    else:
        throttle_type = 'recipient'
        throttle_kind = 'inbound'

    sql = """
        SELECT id, account, priority, period, max_msgs, max_quota, max_rcpts, msg_size
          FROM throttle
         WHERE kind=%s AND account IN %s
         ORDER BY priority DESC
         """ % (sqlquote(throttle_kind), sqlquote(possible_addrs))

    logger.debug('[SQL] Query throttle setting: {}'.format(sql))
    qr = conn.execute(sql)
    throttle_records = qr.fetchall()

    logger.debug('[SQL] Query result: {}'.format(throttle_records))

    if not throttle_records:
        logger.debug('No {} throttle setting.'.format(throttle_type))
        return SMTP_ACTIONS['default']

    # Time of now. used for init_time and last_time.
    now = int(time.time())

    # Throttle setting per rule: max_msgs, max_size, max_rcpts.
    # Sample:
    #
    # t_settings = {
    #   "max_msgs": {
    #       "tid": xx,      # value of `throttle.id`
    #       "account": xx,  # value of `throttle.account`
    #       "value": xx,    # value of `throttle.max_msgs`
    #       "period": xx,   # value of `throttle.period`
    #
    #       "tracking_id": xx,          # value of `throttle_tracking.id`
    #       "cur_msgs": xx,             # value of `throttle_tracking.cur_msgs`
    #       "cur_quota": xx,            # value of `throttle_tracking.cur_quota`
    #       "init_time": xx,            # value of `throttle_tracking.init_time`
    #       "last_time": xx,            # value of `throttle_tracking.last_time`
    #       "last_notify_time": xx,     # value of `throttle_tracking.last_notify_time`
    #
    #       "track_key": xx,            # meta:
    #       ...
    #   },
    #   "max_quota": {
    #       ...
    #   },
    # }
    t_settings = {}

    t_setting_ids = {}
    t_setting_rules = {}    # {(throttle_id, throttle_account): ["max_msgs", "max_rcpts", ...]}

    # Inherit throttle settings with lower priority.
    continue_check_msg_size = True
    continue_check_max_msgs = True
    continue_check_max_quota = True
    continue_check_max_rcpts = True

    # print detailed throttle setting
    throttle_info = ''

    # sql `WHERE` statements used to track throttle.
    # (tid = tid AND account = `user`)
    tracking_sql_where = set()

    for rcd in throttle_records:
        (_id, _account, _priority, _period, _max_msgs, _max_quota, _max_rcpts, _msg_size) = rcd

        # Skip throttle setting which doesn't have period
        if not _period:
            continue

        t_setting_rules[(_id, _account)] = []
        t_setting_ids[_id] = _account

        tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sqlquote(client_address)))

        # No throttle tracking required for `msg_size` rule.
        if continue_check_msg_size and _msg_size >= 0:
            continue_check_msg_size = False

            t_settings['msg_size'] = {
                'tid': _id,
                'account': _account,
                'value': _msg_size,
            }

            t_setting_rules[(_id, _account)].append('msg_size')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'id=%(tid)d/msg_size=%(value)d (bytes)/account=%(account)s; ' % t_settings['msg_size']

        # No throttle tracking required for `max_rcpts` rule.
        if continue_check_max_rcpts and _max_rcpts >= 0:
            continue_check_max_rcpts = False

            t_settings['max_rcpts'] = {
                'tid': _id,
                'account': _account,
                'value': _max_rcpts,
            }

            t_setting_rules[(_id, _account)].append('max_rcpts')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'id=%(tid)d/max_rcpts=%(value)d/account=%(account)s; ' % t_settings['max_rcpts']

        if continue_check_max_msgs and _max_msgs >= 0:
            continue_check_max_msgs = False
            t_settings['max_msgs'] = {'tid': _id,
                                      'account': _account,
                                      'period': _period,
                                      'value': _max_msgs,
                                      'tracking_id': None,
                                      'cur_msgs': 0,
                                      'cur_quota': 0,
                                      'init_time': 0,
                                      'track_key': []}

            t_setting_rules[(_id, _account)].append('max_msgs')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'id=%(tid)d/max_msgs=%(value)d/account=%(account)s; ' % t_settings['max_msgs']

        if continue_check_max_quota and _max_quota >= 0:
            continue_check_max_quota = False
            t_settings['max_quota'] = {'tid': _id,
                                       'account': _account,
                                       'period': _period,
                                       'value': _max_quota,
                                       'tracking_id': None,
                                       'cur_msgs': 0,
                                       'cur_quota': 0,
                                       'init_time': 0,
                                       'track_key': []}
            t_setting_rules[(_id, _account)].append('max_quota')
            tracking_sql_where.add('(tid=%d AND account=%s)' % (_id, sql_user))
            throttle_info += 'id=%(tid)d/max_quota=%(value)d (bytes)/account=%(account)s; ' % t_settings['max_quota']

    if not t_settings:
        logger.debug('No valid {} throttle setting.'.format(throttle_type))
        return SMTP_ACTIONS['default']
    else:
        logger.debug('{} throttle setting: {}'.format(throttle_type, throttle_info))

    # Check `msg_size`, it doesn't require throttle tracking.
    if 'msg_size' in t_settings:
        # Remove it to avoid further use.
        ts = t_settings.pop("msg_size")
        msg_size = ts["value"]

        # Check message size
        if size > msg_size > 0:
            logger.info('[{}] [{}] Quota exceeded: {} throttle for '
                        'msg_size, current: {} bytes. '
                        '({})'.format(client_address,
                                      user,
                                      throttle_type,
                                      size,
                                      throttle_info))

            return SMTP_ACTIONS['reject_msg_size_exceeded']

    # Check `max_rcpts`, it doesn't require throttle tracking.
    if 'max_rcpts' in t_settings:
        # Remove it to avoid further use.
        ts = t_settings.pop("max_rcpts")
        max_rcpts = ts["value"]

        # Check recipient count.
        if recipient_count > max_rcpts > 0:
            logger.info('[{}] [{}] Quota exceeded: {} throttle for '
                        'max_rcpts, current: {}. '
                        '({})'.format(client_address,
                                      user,
                                      throttle_type,
                                      recipient_count,
                                      throttle_info))

            return SMTP_ACTIONS['reject_max_rcpts_exceeded']

    # Update track_key.
    for (_, ts) in list(t_settings.items()):
        t_account = ts['account']
        addr_type = utils.is_valid_amavisd_address(t_account)

        if addr_type in ['ip', 'catchall_ip']:
            # Track based on IP address
            ts['track_key'].append(client_address)
        elif addr_type in ['wildcard_ip', 'wildcard_addr']:
            # Track based on wildcard IP or sender address
            ts['track_key'].append(t_account)
        else:
            # Track based on sender email address
            ts['track_key'].append(user)

    # Get throttle tracking data.
    # Construct SQL query WHERE statement
    sql = """SELECT id, tid, account, cur_msgs, cur_quota, init_time, last_time, last_notify_time
               FROM throttle_tracking
              WHERE %s
              """ % ' OR '.join(tracking_sql_where)

    logger.debug('[SQL] Query throttle tracking data: {}'.format(sql))
    qr = conn.execute(sql)
    tracking_records = qr.fetchall()

    logger.debug('[SQL] Query result: {}'.format(tracking_records))

    # {(throttle_id, account): tracking_id}
    tracking_ids = {}

    # Expired tracking records.
    # Value is a list of value of sql column `throttle_tracking.id`.
    #
    # If one throttle setting has multiple rules (e.g. max_msgs, max_quota),
    # we populate multiple keys in a dict to track each rule, if we loop
    # the dict and update tracking data one by one, latter one overrides
    # earlier ones and causes incorrect data, so we must track different
    # tracking records populated by same throttle setting to maintain
    # correct tracking data.
    expired_tracking_ids = set()

    for rcd in tracking_records:
        (_id, _tid, _account, _cur_msgs, _cur_quota, _init_time, _last_time, _last_notify_time) = rcd

        tracking_ids[(_tid, _account)] = _id

        if not _init_time:
            _init_time = now

        # Get special throttle rule name: msg_size, max_msgs, max_quota
        t_setting_account = t_setting_ids[_tid]
        for rule in t_setting_rules.get((_tid, t_setting_account)):
            if rule in t_settings:
                t_settings[rule]['tracking_id'] = _id
                t_settings[rule]['cur_msgs'] = _cur_msgs
                t_settings[rule]['cur_quota'] = _cur_quota
                t_settings[rule]['init_time'] = _init_time
                t_settings[rule]['last_time'] = _last_time
                t_settings[rule]['last_notify_time'] = _last_notify_time

    if 'max_msgs' in t_settings:
        ts = t_settings['max_msgs']
        max_msgs = ts['value']
        _cur_msgs = ts['cur_msgs']

        _tracking_id = ts['tracking_id']
        _period = int(ts.get('period', 0))
        _init_time = int(ts.get('init_time', 0))
        _last_time = int(ts.get('last_time', 0))
        _last_notify_time = int(ts.get('last_notify_time', 0))

        if _period and (_init_time > 0) and now > (_init_time + _period):
            logger.debug('Existing max_msgs tracking expired, reset.')
            expired_tracking_ids.add(_tracking_id)
            _cur_msgs = 0
            _init_time = now
            _last_time = now

        _requested_max_msgs = _cur_msgs + recipient_count
        if _requested_max_msgs > max_msgs > 0:
            logger.info('[{}] [{}] Quota exceeded: {} throttle for '
                        'max_msgs, recipient_count={}, {}->{}/{}. '
                        '({})'.format(client_address,
                                      user,
                                      throttle_type,
                                      recipient_count,
                                      _cur_msgs,
                                      _requested_max_msgs,
                                      max_msgs,
                                      throttle_info))

            # Send notification email if matches any of:
            # 1: first exceed
            # 2: last notify time is not between _init_time and (_init_time + _period)
            if (not _last_notify_time) or (not (_init_time < _last_notify_time <= (_init_time + _period))):
                __sendmail(conn=conn,
                           user=user,
                           client_address=client_address,
                           throttle_tracking_id=_tracking_id,
                           throttle_name='max_msgs',
                           throttle_value=max_msgs,
                           throttle_kind=throttle_kind,
                           throttle_info=throttle_info)

            return SMTP_ACTIONS['reject_quota_exceeded']
        else:
            # Show the time tracking record is about to expire
            _left_seconds = _init_time + _period - _last_time

            logger.info('[{}] {} throttle, {} -> max_msgs '
                        '({}->{}/{}, period: {} seconds, '
                        '{})'.format(client_address,
                                     throttle_type,
                                     user,
                                     _cur_msgs,
                                     _requested_max_msgs,
                                     max_msgs,
                                     _period,
                                     utils.pretty_left_seconds(_left_seconds)))

    if 'max_quota' in t_settings:
        ts = t_settings['max_quota']
        max_quota = ts['value']
        _cur_quota = ts.get('cur_quota', 0)

        _tracking_id = ts['tracking_id']
        _period = int(ts.get('period', 0))
        _init_time = int(ts.get('init_time', 0))
        _last_time = int(ts.get('last_time', 0))

        if _period and (_init_time > 0) and now > (_init_time + _period):
            # tracking record expired
            logger.info('Existing max_quota tracking expired, reset.')
            expired_tracking_ids.add(_tracking_id)
            _init_time = now
            _last_time = now
            _cur_quota = 0

        if _cur_quota > max_quota > 0:
            logger.info('[{}] [{}] Quota exceeded: {} throttle for '
                        'max_quota, current: {}. ({})'.format(client_address,
                                                              user,
                                                              throttle_type,
                                                              _cur_quota,
                                                              throttle_info))

            if (not _last_notify_time) or (not (_init_time < _last_notify_time <= (_init_time + _period))):
                __sendmail(conn=conn,
                           user=user,
                           client_address=client_address,
                           throttle_tracking_id=_tracking_id,
                           throttle_name='max_quota',
                           throttle_value=max_quota,
                           throttle_kind=throttle_kind,
                           throttle_info=throttle_info,
                           throttle_value_unit='bytes')

            return SMTP_ACTIONS['reject_quota_exceeded']
        else:
            # Show the time tracking record is about to expire
            _left_seconds = _init_time + _period - _last_time

            logger.info('[{}] {} throttle, {} -> max_quota '
                        '({}/{}, period: {} seconds, '
                        '{})'.format(client_address,
                                     throttle_type,
                                     user,
                                     _cur_quota,
                                     max_quota,
                                     _period,
                                     utils.pretty_left_seconds(_left_seconds)))

    # Update tracking record.
    #
    # SQL statements used to add or update tracking data if smtp session is not rejected:
    # {
    #   (tid, k): "...",
    #   ...
    # }
    sql_inserts = {}

    # {(tid, k): ['last_time=xxx', 'init_time=xxx', ...]}
    # {
    #   (tid, k): {
    #       "init_time": xx,
    #       "last_time": xx,
    #       "cur_msgs": xx,
    #   },
    # }
    sql_updates = {}

    # Caution: if one throttle setting has 2 or more rules (e.g. max_msgs + max_rcpts),
    # tracking data will be overwritten by the latter one.

    for (rule, ts) in list(t_settings.items()):
        tid = ts['tid']

        for k in ts['track_key']:
            key = (tid, k)

            if key in tracking_ids:
                # Update existing tracking records
                tracking_id = tracking_ids[key]

                if tracking_id not in sql_updates:
                    sql_updates[tracking_id] = {'id': tracking_id}

                # Store period, used while cleaning up old tracking records.
                sql_updates[tracking_id]['period'] = ts['period']
                sql_updates[tracking_id]['last_time'] = now

                if tracking_id in expired_tracking_ids:
                    # Reset `init_time`, `cur_msgs`, `cur_quota`.
                    sql_updates[tracking_id]['init_time'] = now
                    sql_updates[tracking_id]['cur_msgs'] = recipient_count
                    sql_updates[tracking_id]['cur_quota'] = size
                else:
                    # keep original `init_time`, increase `cur_msgs` and `cur_quota`.
                    sql_updates[tracking_id]['init_time'] = ts['init_time']
                    sql_updates[tracking_id]['cur_msgs'] = 'cur_msgs + %d' % recipient_count
                    sql_updates[tracking_id]['cur_quota'] = 'cur_quota + %d' % size
            else:
                # no tracking record. insert new one.
                # (tid, account, cur_msgs, period, cur_quota, init_time, last_time)
                if key not in sql_inserts:
                    _sql = '(%d, %s, %d, %d, %d, %d, %d)' % (tid, sqlquote(k), recipient_count, ts['period'], size, now, now)
                    sql_inserts[key] = _sql

    if sql_inserts:
        try:
            values = set(sql_inserts.values())
            sql = """INSERT INTO throttle_tracking
                                 (tid, account, cur_msgs, period, cur_quota, init_time, last_time)
                          VALUES """
            sql += ','.join(values)

            logger.debug('[SQL] Insert new tracking record(s): {}'.format(sql))
            conn.execute(sql)
        except Exception as e:
            logger.error("Failed in inserting new throttle tracking record(s): {}".format(e))

    for (_tracking_id, _kv) in list(sql_updates.items()):
        _sql = """UPDATE throttle_tracking
                     SET period={},
                         last_time={},
                         init_time={},
                         cur_msgs={},
                         cur_quota={}
                   WHERE id={}""".format(_kv['period'],
                                         _kv['last_time'],
                                         _kv['init_time'],
                                         _kv['cur_msgs'],
                                         _kv['cur_quota'],
                                         _tracking_id)

        logger.debug('[SQL] Update tracking record: {}'.format(_sql))

        try:
            conn.execute(_sql)
        except Exception as e:
            logger.error("[SQL] Failed in updating throttle tracking data: {}".format(e))

    logger.debug('[OK] Passed all {} throttle settings.'.format(throttle_type))
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
    size = smtp_session_data['size']
    recipient_count = int(smtp_session_data['recipient_count'])

    if size:
        size = int(size)
    else:
        size = 0

    if sender_domain == recipient_domain and settings.THROTTLE_BYPASS_SAME_DOMAIN:
        logger.debug('Bypassed. Sender domain is same as recipient domain.')
        return SMTP_ACTIONS['default']

    if settings.THROTTLE_BYPASS_MYNETWORKS:
        if utils.is_trusted_client(client_address):
            return SMTP_ACTIONS['default']

    # If no smtp auth (sasl_username=<empty>), and not sent from trusted
    # clients, consider it as external sender.
    is_external_sender = True
    if kwargs['sasl_username']:
        logger.debug('Found sasl_username, consider this sender as an internal sender.')
        is_external_sender = False
    else:
        # Consider email from localhost as outbound.
        # SOGo groupware doesn't perform SMTP authentication if it's running
        # on same host as SMTP server.
        if client_address in ['127.0.0.1', '::1']:
            is_external_sender = False

    # Apply sender throttling to only sasl auth users.
    logger.debug('Check sender throttling.')
    action = apply_throttle(conn=conn,
                            conn_vmail=conn_vmail,
                            user=sender,
                            client_address=client_address,
                            size=size,
                            recipient_count=recipient_count,
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
                                size=size,
                                recipient_count=recipient_count,
                                is_sender_throttling=False)

        if not action.startswith('DUNNO'):
            return action

    return SMTP_ACTIONS['default']
