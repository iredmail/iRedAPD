"""Reject sender login mismatch (sender in mail header and SASL username).

You should remove "sender_login_mismatch" in Postfix
"smtpd_sender_restrictions" and let this plugin do it for you.
"""

import logging
from libs import SMTP_ACTIONS

REQUIRE_LOCAL_SENDER = False
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = []
RECIPIENT_SEARCH_ATTRLIST = []

# Allow sender login mismatch for below senders.
ALLOWED_SENDERS = []

def restriction(**kwargs):
    # The sender appears in 'From:' header.
    sender = kwargs['sender']

    # Username used to perform SMTP auth
    sasl_username = kwargs['smtp_session_data'].get('sasl_username', '').lower()

    logging.debug('Sender: %s, SASL username: %s' % (sender, sasl_username))

    if sasl_username:    # Is a outgoing email
        # Compare them
        if sender != sasl_username:
            if sasl_username in ALLOWED_SENDERS:
                return SMTP_ACTIONS['default']
            else:
                # Reject without reason.
                #return SMTP_ACTIONS['reject']

                # Reject with reason.
                # There must be a space between smtp action and reason text.
                return SMTP_ACTIONS['reject'] + ' ' + 'Sender login mismatch.'

                # Log message without reject.
                #logging.info('Sender login mismatch.')

    return SMTP_ACTIONS['default']
