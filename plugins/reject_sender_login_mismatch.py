# Author: Zhang Huangbin <zhb _at_ iredmail.org>

# Purpose: Reject sender login mismatch (addresses in 'From:' and SASL username).

# How to use this plugin:
#
# *) You must remove "sender_login_mismatch" restriction rule in Postfix
#    setting "smtpd_sender_restrictions" (/etc/postfix/main.cf). this plugin
#    will do the same restriction for you.
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#    plugins = ['reject_sender_login_mismatch', ...]
#
# *) List senders who are allowed to send email as different users in iRedAPD
#    config file (/opt/iredapd/settings.py), in parameter
#    ALLOWED_LOGIN_MISMATCH_SENDERS. For example:
#
#    ALLOWED_LOGIN_MISMATCH_SENDERS = ['user1@here.com', 'user2@here.com']
#

import logging
from libs import SMTP_ACTIONS
import settings


# Allowed senders.
try:
    ALLOWED_LOGIN_MISMATCH_SENDERS = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
except AttributeError:
    ALLOWED_LOGIN_MISMATCH_SENDERS = []


def restriction(**kwargs):
    sender = kwargs['sender']
    sasl_username = kwargs['sasl_username']

    logging.debug('Allowed SASL username: %s' % ', '.join(ALLOWED_LOGIN_MISMATCH_SENDERS))
    logging.debug('Sender: %s, SASL username: %s' % (sender, sasl_username))

    # Apply on outgoing emails
    if sasl_username:
        if sender != sasl_username:
            if sasl_username in ALLOWED_LOGIN_MISMATCH_SENDERS:
                return SMTP_ACTIONS['default']
            else:
                # Reject with reason.
                # There must be a space between smtp action and reason text.
                return SMTP_ACTIONS['reject'] + ' Sender login mismatch.'

                # Log message without reject.
                #logging.info('Sender login mismatch.')

    return SMTP_ACTIONS['default']
