# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Reject message submitted by sasl authenticated user but specifying
#          null sender in 'From:' header (from=<> in Postfix log).
#
# How to use this plugin:
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#    plugins = ['reject_null_sender', ...]
#
# *) Restart iRedAPD service.

import logging
from libs import SMTP_ACTIONS


def restriction(**kwargs):
    sender = kwargs['sender']
    sasl_username = kwargs['sasl_username']

    if sasl_username and not sender:
        logging.debug('Possible spam (sasl authenticated but send as null sender).')
        return SMTP_ACTIONS['reject']

    return SMTP_ACTIONS['default']
