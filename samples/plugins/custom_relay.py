# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Return different relayhost for outgoing emails based on sender
#          domain and message size.

# Usage:
#
#   * Create required SQL table
#       - For SQL backends, please create it in `vmail` database
#       - For LDAP backends, please create it in `iredapd` database
"""
CREATE TABLE IF NOT EXISTS `custom_relay` (
    `id`        BIGINT(20) UNSIGNED AUTO_INCREMENT,
    `account`   VARCHAR(100) NOT NULL DEFAULT '',
    `priority`  TINYINT(2) NOT NULL DEFAULT 0,
    `min_size`  BIGINT(10) UNSIGNED,
    `max_size`  BIGINT(10) UNSIGNED,
    `relayhost` VARCHAR(255) NOT NULL DEFAULT '',
    PRIMARY KEY (`id`),
    INDEX (`account`),
    INDEX (`priority`),
    INDEX (`min_size`),
    INDEX (`max_size`)
) ENGINE=InnoDB;
"""
#
#   * Add a new parameter in iRedAPD config file /opt/iredapd/settings.py:
#
#       CUSTOM_RELAY_DEFAULT_RELAY = 'smtp-amavis:[127.0.0.1]:10025'
#
#     This parameter controls which content-filter program we should use if
#     email recipient is hosted locally.

###################
# SQL columns:
#
#   - `min_size`, `max_size`: message size in bytes. value 0 means unlimited.
#   - `account`: Possible values:
#
#       - @.                  # global/default setting
#       - @domain.com.uk      # per-domain
#       - @.domain.com.uk     # domain and all sub-domains
#       - @com.uk
#       - @.com.uk
#       - @.uk
#       - user@domain.com     # single user
#
#   - `priority`: Priority of different accounts, largest number has highest
#                 priority. Possible values:
#
#       - 0: lowest priority. used for global settings.
#       - 10: per-domain priority.
#       - 20: per-user priority.
#
# This plugin will query sql table with statement like this:
#
#       SELECT relayhost
#         FROM custom_relay
#        WHERE account IN %(accounts)s
#              AND ((min_size  = 0        AND max_size >= %(size)d)
#                OR (min_size <= %(size)d AND max_size >= %(size)d)
#                OR (min_size  < %(size)d AND max_size  = 0)
#                OR (min_size = 0 AND max_size = 0))
#     ORDER BY priority ASC
#        LIMIT 1
#
# In above sql query, `%(accounts)s` will be replaced by possible policy
# senders, `%(size)d` will be replaced by the real message size (in byte).
#
##################
# Sample settings
#
# *) Global / default / catch-all settings (with account='@.', priority=0)
#
#   -- size from 0 to 10485760 bytes (10MB)
#   sql> INSERT INTO custom_relay (account, priority, min_size, max_size, relayhost)
#                          VALUES ('@.', 0, 0, 10485760, 'smtp:[server-1.com]:25');
#
#   -- size from 10485761 bytes (10MB + 1 byte) to 20971520 bytes (20MB)
#   sql> INSERT INTO custom_relay (account, priority, min_size, max_size, relayhost)
#                          VALUES ('@.', 0, 10485761, 20971520, 'smtp:[server-2.com]:25');
#
#   -- size from 20971521 bytes (20MB + 1 byte) to 0 (unlimited)
#   sql> INSERT INTO custom_relay (account, priority, min_size, max_size, relayhost)
#                          VALUES ('@.', 0, 20971521, 0, 'smtp:[server-2.com]:25');
#
# *) Per-domain settings for iredmail.org (with account='@iredmail.org', priority=10)
#
#   -- size from 0 to 10485760 bytes (10MB)
#   sql> INSERT INTO custom_relay (account, priority, min_size, max_size, relayhost)
#                          VALUES ('@iredmail.org', 10, 0, 10485760, 'smtp:[server-1.com]:25');
#
#   -- size from 10485761 bytes (10MB + 1 byte) to 20971520 bytes (20MB)
#   sql> INSERT INTO custom_relay (account, priority, min_size, max_size, relayhost)
#                          VALUES ('@iredmail.org', 10, 10485761, 20971520, 'smtp:[server-2.com]:25');
#
#   -- size from 20971521 bytes (20MB + 1 byte) to 0 (unlimited)
#   sql> INSERT INTO custom_relay (account, priority, min_size, max_size, relayhost)
#                          VALUES ('@iredmail.org', 10, 20971521, 0, 'smtp:[server-2.com]:25');

from web import sqlquote

from libs.logger import logger
from libs import SMTP_ACTIONS
from libs import utils
import settings

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import is_local_domain
else:
    from libs.sql import is_local_domain

SMTP_PROTOCOL_STATE = ['RCPT', 'END-OF-MESSAGE']

# Get relay for local recipient
try:
    relay_for_local_recipient = settings.CUSTOM_RELAY_DEFAULT_RELAY
except:
    relay_for_local_recipient = 'smtp-amavis:[127.0.0.1]:10025'


def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']
    sasl_username_domain = kwargs['sasl_username_domain']

    if not sasl_username:
        logger.debug('SKIP, not an email sent from an authenticated user (no sasl_username found).')
        return SMTP_ACTIONS['default']

    try:
        size = int(kwargs['smtp_session_data']['size'])
    except Exception as e:
        logger.error('SKIP, cannot get mail message size. Error: %s' % repr(e))
        return SMTP_ACTIONS['default']

    policy_accounts = [sasl_username] + utils.get_policy_addresses_from_email(sasl_username)

    # Get db cursor
    conn_vmail = kwargs['conn_vmail']
    if settings.backend == 'ldap':
        conn_relay = kwargs['conn_iredapd']
    else:
        conn_relay = kwargs['conn_vmail']

    recipient_domain = kwargs['recipient_domain']
    if kwargs['smtp_session_data']['protocol_state'] == 'RCPT':
        if sasl_username_domain == recipient_domain:
            logger.debug('SASL username domain is same as recipient domain ({}), use default relay: {}'.format(recipient_domain, relay_for_local_recipient))
            return 'FILTER %s' % relay_for_local_recipient

        if is_local_domain(conn=conn_vmail, domain=recipient_domain, include_backupmx=True):
            logger.debug('Recipient domain ({}) is locally hosted, use default relay: {}'.format(recipient_domain, relay_for_local_recipient))
            return 'FILTER %s' % relay_for_local_recipient

    if kwargs['smtp_session_data']['protocol_state'] == 'END-OF-MESSAGE':
        logger.debug('Recipient domain (%s) is NOT locally hosted.' % relay_for_local_recipient)

        # Query sql db to get highest custom relayhost.
        sql = """
            SELECT relayhost
              FROM custom_relay
             WHERE account IN %(accounts)s
                   AND ((min_size  = 0        AND max_size >= %(size)d)
                        OR (min_size <= %(size)d AND max_size >= %(size)d)
                        OR (min_size  < %(size)d AND max_size  = 0)
                        OR (min_size = 0 AND max_size = 0))
         ORDER BY priority ASC
            LIMIT 1
            """ % {'size': size, 'accounts': sqlquote(policy_accounts)}

        logger.debug('[SQL] Query custom relayhost with highest priority: \n%s' % sql)

        try:
            qr = utils.execute_sql(conn_relay, sql)
            qr_relay = qr.fetchone()[0]

            logger.debug('[SQL] Query result: %s' % qr_relay)
        except Exception as e:
            logger.error('Error while querying custom relayhost (fallback to default action): %s' % repr(e))
            return SMTP_ACTIONS['default']

        if qr_relay:
            logger.debug('Return custom relayhost: %s' % qr_relay)
            return 'FILTER %s' % qr_relay
        else:
            logger.debug('No custom relayhost, return default action.')
            return SMTP_ACTIONS['default']

    return SMTP_ACTIONS['default']
