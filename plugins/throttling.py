# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: per-account inbound/outbound throttling.

# Note: To keep the database compact, you should set up a daily cron job to
#       old/inactive records.

# Usage
#
# *) Enable iRedAPD in Postfix `smtpd_end_of_data_restrictions`.
#    For example:
#
#    smtpd_end_of_data_restrictions =
#           check_policy_service inet:[127.0.0.1]:7777,
#           ...
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py.
# *) Restart both iRedAPD and Postfix services.

# Technology details
#
# *) Sender Throttling
#
# Currently you may throttle based on amount of mails and total mail size
# sent over a given period of time.
#
# Eg: You can enforce that user@domain.com does not send more than 1000 mails
# or 1GB of mail (whichever limit is hit first) in say a 5 minute period.
#
# Possible sender throttling methods:
#
# 1) Throttle by sender address (either SASL username or From: address).
#    Valid sender addresses are:
#
#       *) Full sender email address: user@domain.com
#       *) Domain name (with a prefixed '@'): @domain.com
#       *) Sub-domain name (with a prefixed '@.'): @.domain.com
#       *) IP address:  192.168.1.1
#       *) IP network:  192.168.1.*
#
#   Priorities (larger digital number has higher priority):
#
#       *) ip: 10,
#       *) email: 8,
#       *) wildcard_addr: 6,     # r'user@*'. used in iRedAPD plugin `amavisd_wblist`
#                                # as wildcard sender. e.g. 'user@*'
#       *) domain: 5,
#       *) subdomain: 3,
#       *) top_level_domain: 1,
#       *) catchall: 0,

#
#   1.1) based on full sender email address (user@domain.com).
#
#   INSERT INTO throttle (sender, max_msgs, max_quota, msg_size, period, date, priority)
#                 VALUES ('user@domain.com',    # from address
#                         50,                   # maximum messages per time unit
#                         250000000,            # size in bytes (250 megs) (maximum is 2gig)
#                         10240000,             # maximum message size (10 meg)
#                         86400,                # time unit in seconds (1 day)
#                         UNIX_TIMESTAMP(),     # current time
#                         10);                  # priority of record
#
#   1.2) based on domain name (@domain.com).
#
#   INSERT INTO throttle (sender, max_msgs, max_quota, msg_size, period, date, priority)
#                 VALUES ('@domain.com',        # domain
#                         50,                   # maximum messages per time unit
#                         250000000,            # size in bytes (250 megs) (maximum is 2gig)
#                         10240000,             # maximum message size (10 meg)
#                         86400,                # time unit in seconds (1 day)
#                         UNIX_TIMESTAMP(),     # current time
#                         5);                   # priority of record
#
#  Do take note of the "priority" record as this allows you to have
#  global limits for a specific domain, but if there are specific
#  accounts that need their own dedicated/specific/unique limit then
#  you can add their records but with a higher priority.
#
# 2) Throttle by SASL user name
#
#INSERT INTO throttle
#(_from,_count_max,_quota_max,_time_limit,_mail_size,_date)
# VALUES ('SASL_username',    # from address, SASL username or ip address
#          50,                # maximum messages per time unit
#          250000000,         # size in bytes (250 megs)
#          86400,             # time unit in seconds (1 day)
#          10240000,          # maximum message size (10 meg)
#          UNIX_TIMESTAMP()); # current time
#
# 3) Throttle by IP address
#
#INSERT INTO throttle \
# (_from,_count_max,_quota_max,_time_limit,_mail_size,_date,_priority)
# VALUES ('192.168.0.1',      # from address
#          50,                # maximum messages per time unit
#          250000000,         # size in bytes (250 megs) (maximum is 2gig)
#          86400,             # time unit in seconds (1 day)
#          10240000,          # maximum message size (10 meg)
#          UNIX_TIMESTAMP(),  # current time
#          10);               # priority of record
#
#  OR netblock:
#
#INSERT INTO throttle \
# (_from,_count_max,_quota_max,_time_limit,_mail_size,_date,_priority)
# VALUES ('192.168.0.%',      # domain
#          50,                # maximum messages per time unit
#          250000000,         # size in bytes (250 megs) (maximum is 2gig)
#          86400,             # time unit in seconds (1 day)
#          10240000,          # maximum message size (10 meg)
#          UNIX_TIMESTAMP(),  # current time
#          5);                # priority of record
#
#  Upon the first time a sender sends a mail through the sender
#  throttling module, if they do not exist in the database, the
#  module will grab the configuration defaults from policyd.conf
#  and those values will be inserted into the database. You can
#  at a later stage (if you wish) increase those limits by changing
#  the values in MySQL. If you wish to create users immediately
#  with higher values, you can do the following:
#
#  If you enable throttling by SASL and a client connects to
#  Postfix without SASL info, by default Policyd will automatically
#  use the MAIL FROM: address so nothing breaks.
#
#  To keep the database compact and remove inactive entries, you can
#  set a time limit for automatic cleanup.
#
#
#  *)Recipient Throttling
#
#  Recipient Throttling module allows quota enforcement. An example
#  of where this module is useful are if people maintain SMS gateways
#  and have requirements that SMS abuse does not occur. Also this is
# useful on outgoing smtp/relays during virus outbreaks. Recent
# virus outbreaks had a few infected machines flooding the same
# recipients over and over.
#
# You can enforce that no user receives more than 1000 mails in a
# given time period.

# Upon the first delivery a recipient receives, if they do not exist
# in the database, the module will grab the configuration defaults
# from policyd.conf and those values will be inserted into the
# database. You can at a later stage (if you wish) increase those
# limits by changing the values in MySQL. If you want to create
# users immediately with high values, you can do the following:
#
#INSERT INTO throttle_rcpt (_rcpt,_count_max,_time_limit)
# VALUES ('camis@mweb.co.za', # recipient address
#          100,               # maximum messages per time unit
#          86400,             # time unit in seconds (1 day)
#          UNIX_TIMESTAMP()); # current time
#
#

import time
import logging
from web import sqlliteral
import settings
from libs import SMTP_ACTIONS
from libs.utils import sqllist, is_trusted_client
from libs.amavisd.core import get_valid_addresses_from_email

SMTP_PROTOCOL_STATE = ['RCPT', 'END-OF-MESSAGE']

# Connect to iredapd database
REQUIRE_IREDAPD_DB = True


def convert_throttle_setting_to_dict(s, value_is_integer=True):
    """Convert throttle setting string to dict.

    >>> convert_throttle_setting_to_dict('var:value;var2:value2;var3:vavlue3;')
    {'var': value,
     'var2': value2,
     'var3': value3}
    """

    if not s:
        return {}

    sd = {}

    # Get all single setting
    setting_items = [st for st in s.split(';') if ':' in st]
    for item in setting_items:
        if item:
            key, value = item.split(':')

            if value_is_integer:
                try:
                    value = int(value)
                except:
                    pass

            sd[key] = value

    return sd


# Apply throttle setting and return smtp action.
def apply_throttle(conn,
                   user,
                   client_address,
                   protocol_state,
                   size,
                   is_sender_throttling=True):
    possible_addrs = get_valid_addresses_from_email(user)
    possible_addrs.append(client_address)

    logging.debug('Possible addresses: %s' % str(possible_addrs))

    if is_sender_throttling:
        col_period = 'period'
        col_init_time = 'init_time'
        col_last_time = 'last_time'
        col_total_msgs = 'total_msgs'
        col_total_quota = 'total_quota'
        col_cur_msgs = 'cur_msgs'
        col_cur_quota = 'cur_quota'
        col_max_msgs = 'max_msgs'
        col_max_quota = 'max_quota'
        col_msg_size = 'msg_size'
    else:
        col_period = 'rcpt_period'
        col_init_time = 'rcpt_init_time'
        col_last_time = 'rcpt_last_time'
        col_total_msgs = 'rcpt_total_msgs'
        col_total_quota = 'rcpt_total_quota'
        col_cur_msgs = 'rcpt_cur_msgs'
        col_cur_quota = 'rcpt_cur_quota'
        col_max_msgs = 'rcpt_max_msgs'
        col_max_quota = 'rcpt_max_quota'
        col_msg_size = 'rcpt_msg_size'

    # TODO Query all available throttle setting. If no particular throttle
    #       setting (e.g. no throttle for `max_msgs` or `max_quota`) with
    #       higher priority, check throttle with lower priority.
    #
    # Questions:
    #
    #   * use `max_msgs=-1` to force check setting with lower priority
    #   * use `max_msgs=0` as no limit, and stop checking settings with lower priority.
    sql = """
        SELECT id, user, settings, priority, %s,
               %s, %s, %s, %s
          FROM throttle
         WHERE user IN %s
         ORDER BY priority DESC
         LIMIT 1
         """ % (col_period,
                col_cur_msgs, col_cur_quota,
                col_init_time, col_last_time,
                sqllist(possible_addrs))

    logging.debug('[SQL] Query throttle setting: %s' % sql)
    qr = conn.execute(sql)
    sql_record = qr.fetchone()

    logging.debug('[SQL] Query result: %s' % str(sql_record))

    if not sql_record:
        logging.debug('No throttle setting.')
    else:
        (t_id, t_user, t_setting, priority, period,
         cur_msgs, cur_quota, init_time, last_time) = sql_record

        # Parse throttle setting
        throttle_setting = convert_throttle_setting_to_dict(t_setting)

        if settings.log_level == 'debug':
            trtl = 'Throttle setting:\n'
            trtl += '\n'.join(['%20s: %d' % (k, v) for (k, v) in throttle_setting.items()])

            logging.debug(trtl)

        logging.debug('Apply throttle setting for user: %s' % t_user)

        if is_sender_throttling:
            max_msgs = throttle_setting.get(col_max_msgs, 0)
            max_quota = throttle_setting.get(col_max_quota, 0)
            msg_size = throttle_setting.get(col_msg_size, 0)
        else:
            max_msgs = throttle_setting.get(col_max_msgs, 0)
            max_quota = throttle_setting.get(col_max_quota, 0)
            msg_size = throttle_setting.get(col_msg_size, 0)

        # If no period, throttle setting is useless.
        if not period:
            return SMTP_ACTIONS['default']

        # Check `period`
        tracking_expired = False

        now = int(time.time())

        if now > (init_time + period):
            logging.debug('Throttle tracking expired, reset initial tracking time to %d.' % now)
            tracking_expired = True

            # Reset current msgs and quota immediately.
            # Note: we reset `init_time` later in 'END-OF-MESSAGE'.
            cur_msgs = 0
            cur_quota = 0

        # Apply throttle setting on different protocol_state
        #
        # Note: Don't update `cur_msgs` in 'RCPT' protocol state, because
        # this mail may be rejected by other plugins in 'END-OF-MESSAGE' state
        # or other restrictions in Postfix.
        #
        #   * RCPT: max_msgs
        #   * END-OF-MESSAGE: msg_size, max_quota
        if protocol_state == 'RCPT':
            if max_msgs > 0:
                if cur_msgs >= max_msgs:
                    logging.debug('Exceed max messages: cur_msgs (%d) >= max_msgs (%d).' % (cur_msgs, max_msgs))
                    return SMTP_ACTIONS['reject_exceed_max_msgs']
                else:
                    logging.debug('Not exceed max messages: cur_msgs (%d) < max_msgs (%d).' % (cur_msgs, max_msgs))

        elif protocol_state == 'END-OF-MESSAGE':
            # Check message size
            if msg_size > 0 and size > msg_size:
                logging.debug('Exceeded message size for single mail: max=%d, current=%d.' % (msg_size, size))
                return SMTP_ACTIONS['reject_exceed_msg_size']

            # Check max messages
            if max_msgs > 0 and cur_msgs >= max_msgs:
                logging.debug('Exceeded number of mails in total: max=%d, current=%d.' % (max_msgs, cur_msgs))
                return SMTP_ACTIONS['reject_exceed_max_msgs']

            # Check max quota
            if max_quota > 0 and cur_quota >= max_quota:
                logging.debug('Exceeded accumulated message size: max=%d bytes, current=%d (bytes).' % (max_quota, cur_quota))
                return SMTP_ACTIONS['reject_exceed_max_quota']

            # If not rejected, update init_time, cur_msgs, cur_quota, last_time
            sql_update_sets = []
            sql_update_sets.append('%s = %s + 1' % (col_total_msgs, col_total_msgs))
            sql_update_sets.append('%s = %s + %d' % (col_total_quota, col_total_quota, size))

            if tracking_expired:
                # Reset init_time, cur_msgs, max_quota
                sql_update_sets.append('%s = %d' % (col_init_time, int(time.time())))

                if max_msgs:
                    sql_update_sets.append('%s = 1' % col_cur_msgs)

                if max_quota:
                    sql_update_sets.append('%s = %d' % (col_cur_quota, size))

            else:
                if max_msgs:
                    sql_update_sets.append('%s = %s + 1' % (col_cur_msgs, col_cur_msgs))

                if max_quota:
                    sql_update_sets.append('%s = %s + %d' % (col_cur_quota, col_cur_quota, size))

            if sql_update_sets:
                sql_update_sets.append('%s = %d' % (col_last_time, int(time.time())))

                sql_update_set = ','.join(sql_update_sets)
                sql = """
                    UPDATE throttle
                       SET %s
                     WHERE id=%d
                     """ % (sqlliteral(sql_update_set), t_id)
                logging.debug('[SQL] Update throttle tracking: %s' % sql)
                conn.execute(sql)

    return SMTP_ACTIONS['default']


def restriction(**kwargs):
    conn = kwargs['conn_iredapd']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
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
            logging.debug('Client is trusted (listed in MYNETWORKS).')
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
