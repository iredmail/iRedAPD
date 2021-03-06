# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Reject message submitted by sasl authenticated user but specifying
#          null sender in 'From:' header (from=<> in Postfix log).
#
#          If your user's password was cracked by spammer, spammer can use
#          this account to bypass smtp authentication, but with a null sender
#          in 'From:' header, throttling won't be triggered.
#
# How to use this plugin:
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#    plugins = ['reject_null_sender', ...]
#
# *) Restart iRedAPD service.

from libs.logger import logger
from libs import SMTP_ACTIONS


def restriction(**kwargs):
    sender = kwargs['sender']
    sasl_username = kwargs['sasl_username']

    if sasl_username and (not sender):
        logger.info('Possible spam (authenticated as %s but sender address is null).' % sasl_username)
        return SMTP_ACTIONS['reject_null_sender']

    return SMTP_ACTIONS['default']
