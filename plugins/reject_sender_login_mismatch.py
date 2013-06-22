"""Reject sender login mismatch (sender in mail header and SASL username).

*) You should remove "sender_login_mismatch" in Postfix
   "smtpd_sender_restrictions" and let this plugin do it for you.

*) Please list all allowed senders in in iRedAPD config file (settings.py),
   parameter ALLOWED_LOGIN_MISMATCH_SENDERS. For example:

    ALLOWED_LOGIN_MISMATCH_SENDERS = ['user1@here.com', 'user2@here.com']
"""

import logging
from libs import SMTP_ACTIONS
import settings

REQUIRE_LOCAL_SENDER = False
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = []
RECIPIENT_SEARCH_ATTRLIST = []

# Allowed senders.
try:
    ALLOWED_LOGIN_MISMATCH_SENDERS = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
except AttributeError:
    ALLOWED_LOGIN_MISMATCH_SENDERS = []

def restriction(**kwargs):
    # The sender appears in 'From:' header.
    sender = kwargs['sender']

    # Username used to perform SMTP auth
    sasl_username = kwargs['smtp_session_data'].get('sasl_username', '').lower()

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
                return SMTP_ACTIONS['reject'] + ' ' + 'Sender login mismatch.'

                # Log message without reject.
                #logging.info('Sender login mismatch.')

    return SMTP_ACTIONS['default']