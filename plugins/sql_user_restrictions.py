# Author: Zhang Huangbin <zhb _at_ iredmail.org>

# Purpose: Per-user send/receive restrictions.
#
# Required SQL columns of table `vmail.mailbox`.
#   - mailbox.allowedrecipients: Allow user to send TO listed recipients
#   - mailbox.rejectedrecipients: Reject emails sent TO listed recipients
#   - mailbox.allowedsenders: Accept emails FROM listed senders
#   - mailbox.rejectedsenders: Reject emails FROM listed senders
#
# Valid sender/recipient addresses:
#
#   - .*:           all addresses (user, domain, sub-domain)
#   - domain.com:   single domain
#   - .domain.com:  single domain and its all sub-domains
#   - user@domain.com:  single email address

import logging
from web import sqlquote
from libs import SMTP_ACTIONS


def restriction(**kwargs):
    conn = kwargs['conn']
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    # Get restriction rules for sender
    sql = '''
        SELECT
            allowedrecipients, rejectedrecipients,
            allowedsenders, rejectedsenders
        FROM mailbox
        WHERE username=%s
        LIMIT 1
    ''' % sqlquote(sender)
    logging.debug('SQL to get restriction rules of sender (%s): %s' % (sender, sql))

    conn.execute(sql)
    sql_record = conn.fetchone()
    logging.debug('Returned SQL Record: %s' % str(sql_record))

    # Sender account exists, perform recipient restrictions
    if sql_record:
        allowed_recipients, rejected_recipients, allowed_senders, rejected_senders = sql_record

        # If it does have restrictions
        if not allowed_recipients and not rejected_recipients:
            logging.debug('No restrictions of sender.')
        else:
            # Allowed first
            # single recipient, domain, sub-domain, catch-all
            all_allowed_recipients = [s.lower().strip() for s in allowed_recipients.split(',')]
            logging.debug('All allowed recipient: %s' % str(all_allowed_recipients))

            if all_allowed_recipients:
                if recipient in all_allowed_recipients \
                   or recipient_domain in all_allowed_recipients \
                   or '.' + recipient_domain in all_allowed_recipients \
                   or '*' in all_allowed_recipients:
                    return SMTP_ACTIONS['accept']

            all_rejected_recipients = [s.lower().strip() for s in rejected_recipients.split(',')]
            logging.debug('All rejected recipient: %s' % str(all_rejected_recipients))

            if all_rejected_recipients:
                if recipient in all_rejected_recipients \
                   or recipient_domain in all_rejected_recipients \
                   or '.' + recipient_domain in all_rejected_recipients \
                   or '*' in all_rejected_recipients:
                    return SMTP_ACTIONS['reject']

    # Get restriction rules for recipient
    # Don't perform another SQL query if sender == recipient
    if sender != recipient:
        sql = '''
            SELECT
                allowedrecipients, rejectedrecipients,
                allowedsenders, rejectedsenders
            FROM mailbox
            WHERE username=%s
            LIMIT 1
        ''' % sqlquote(recipient)
        logging.debug('SQL to get restriction rules of recipient (%s): %s' % (recipient, sql))

        conn.execute(sql)
        sql_record = conn.fetchone()
        logging.debug('Returned SQL Record: %s' % str(sql_record))

    # Recipient account exists, perform sender restrictions
    if sql_record:
        allowed_recipients, rejected_recipients, allowed_senders, rejected_senders = sql_record

        # If it does have restrictions
        if not allowed_senders and not rejected_senders:
            logging.debug('No restrictions of recipient.')
        else:
            # Allowed first
            # single recipient, domain, sub-domain, catch-all
            all_allowed_senders = [s.lower().strip() for s in allowed_senders.split(',')]
            logging.debug('All allowed senders: %s' % str(all_allowed_senders))

            if all_allowed_senders:
                if sender in all_allowed_senders \
                   or sender_domain in all_allowed_senders \
                   or '.' + sender_domain in all_allowed_senders \
                   or '.*' in all_allowed_senders:
                    return SMTP_ACTIONS['accept']

            all_rejected_senders = [s.lower().strip() for s in rejected_senders.split(',')]
            logging.debug('All rejected senders: %s' % str(all_rejected_senders))

            if all_rejected_senders:
                if sender in all_rejected_senders \
                   or sender_domain in all_rejected_senders \
                   or '.' + sender_domain in all_rejected_senders \
                   or '*' in all_rejected_senders:
                    return SMTP_ACTIONS['reject']

    return SMTP_ACTIONS['default']
