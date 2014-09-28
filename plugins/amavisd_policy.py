# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Check per-recipient policy stored in Amavisd database (used in
#          Amavisd setting '@lookup_sql_dsn').
#
# Available functions:
#
# *) white/blacklist
# *) message size limit
#
# How to use this plugin:
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
# *) Restart both iRedAPD and Postfix services.

# TODO
#
# *) Apply some checking in 'RCPT' state instead of 'END-OF-MESSAGE', so that
#    we can save some system resources. especially bandwidth used to transfer
#    entire message.

import logging
import settings
from libs import SMTP_ACTIONS, utils
from libs.amavisd import core as amavisd_lib

SMTP_PROTOCOL_STATE = 'END-OF-MESSAGE'

# Connect to amavisd database
REQUIRE_AMAVISD_DB = True

def restriction(**kwargs):
    recipient = kwargs['recipient']
    adb_cursor = kwargs['amavisd_db_cursor']

    (status, policy_records) = amavisd_lib.get_applicable_policy(adb_cursor, recipient, **kwargs)
    if not status:
        return SMTP_ACTIONS['default']

    if not policy_records:
        logging.debug('No policy found.')
        return SMTP_ACTIONS['default']

    for rcd in policy_records:
        print rcd

    return SMTP_ACTIONS['default']
