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

from web import sqlquote
from libs import SMTP_ACTIONS

PLUGIN_NAME = 'sql_user_restrictions'

def restriction(dbConn, senderReceiver, smtpSessionData, logger, **kargs):
    #
    # Allow to send to users under same domain and alias domains.
    #
    # Get restrictions for sender
    sql = '''
        SELECT \
            allowedrecipients,rejectedrecipients,\
            allowedsenders,rejectedsenders \
        FROM mailbox \
        WHERE username=%s
        LIMIT 1
    ''' % sqlquote(senderReceiver['sender'])
    logger.debug('SQL: %s' % sql)

    dbConn.execute(sql)
    sql_record = dbConn.fetchone()
    logger.debug('Returned SQL Record: %s' % str(sql_record))

    # Recipient account doesn't exist.
    if not sql_record:
        return 'DUNNO Not a local user'

    allowed_recipients, rejected_recipients, allowed_senders, rejected_senders = sql_record

    # TODO Allowed first

    return SMTP_ACTIONS['default']
