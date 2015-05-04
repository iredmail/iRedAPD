# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Check per-recipient message size limit stored in Amavisd database
#          (column `policy.message_size_limit`), reject email if message size
#          exceeded.
#
# Note: Amavisd is configured to be an after-queue content filter in iRedMail,
#       with '@lookup_sql_dsn' setting enabled in Amavisd config file, Amavisd
#       will query per-recipient, per-domain and server-wide (a.k.a. catch-all)
#       policy rules stored in SQL table `policy`.
#
#       if you don't enable this plugin, Amavisd will still reject email AFTER
#       Postfix queued the email. If you prefer to reject the email BEFORE
#       Postfix queued it to save system resource, you should enable this plugin.
#
# How to use this plugin:
#
# *) Enable `@lookup_sql_dsn` in Amavisd config file.
#
# *) Set Amavisd lookup SQL database related parameters (amavisd_db_*) in
#    iRedAPD config file `settings.py`, and enable this plugin.
#
# *) Enable iRedAPD in Postfix `smtpd_end_of_data_restrictions`.
#    For example:
#
#    smtpd_end_of_data_restrictions =
#           check_policy_service inet:[127.0.0.1]:7777,
#           ...
#
# *) Enable this plugin in iRedAPD config file (/opt/iredapd/settings.py).
# *) Restart both iRedAPD and Postfix services.

import logging
from libs import SMTP_ACTIONS
from libs.amavisd import core as amavisd_lib

SMTP_PROTOCOL_STATE = 'END-OF-MESSAGE'

# Connect to amavisd database
REQUIRE_AMAVISD_DB = True


def restriction(**kwargs):
    conn = kwargs['conn_amavisd']

    recipient = kwargs['recipient']

    # message size in bytes
    msg_size = int(kwargs['smtp_session_data']['size'])
    logging.debug('Message size: %d' % msg_size)

    wanted_policy_columns = ['policy_name', 'message_size_limit']

    (status, policy_records) = amavisd_lib.get_applicable_policy(conn,
                                                                 recipient,
                                                                 policy_columns=wanted_policy_columns,
                                                                 **kwargs)
    if not status:
        return SMTP_ACTIONS['default']

    if not policy_records:
        logging.debug('No policy found.')
        return SMTP_ACTIONS['default']

    for rcd in policy_records:
        (policy_name, size_limit) = rcd
        if not size_limit:
            logging.debug('SKIP: policy_name %s, no valid message_size_limit: %s' % (
                policy_name,
                str(size_limit))
            )
            continue
        else:
            size_limit = int(size_limit)
            if size_limit > msg_size:
                logging.debug('SKIP, limit not reached. policy_name %s has valid message_size_limit: %s' % (
                    policy_name,
                    str(size_limit))
                )
                # Just use the first valid size limit (with highest priority) and skip others.
                break
            else:
                logging.debug('Reject by policy_name %s, message_size_limit: %s' % (
                    policy_name,
                    str(size_limit))
                )
                return SMTP_ACTIONS['reject_message_size_exceeded']

    return SMTP_ACTIONS['default']
