# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: per-account inbound/outbound throttling.
#
# How to use this plugin:
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

import logging
from libs import SMTP_ACTIONS

SMTP_PROTOCOL_STATE = 'END-OF-MESSAGE'

# Connect to amavisd database
REQUIRE_AMAVISD_DB = True


def restriction(**kwargs):
    conn = kwargs['conn_iredapd']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    return SMTP_ACTIONS['default']
