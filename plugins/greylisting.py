# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: greylisting.

import logging
from libs import SMTP_ACTIONS, sqllist
import settings

# Return 4xx with greylisting message to Postfix.
action_greylisting = SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE

def should_be_greylisted(conn, senders):
    """Check if greylisting should be applied to specified senders.

    conn - sql connection cursor
    senders - list of senders we should check greylisting
    """
    sql = """SELECT sender, enable, priority FROM greylisting
             WHERE sender IN %s
             ORDER BY priority DESC""" % sqllist(senders)
    logging.debug('SQL: query policy senders:\n %s' % sql)

    qr = conn.execute(sql)
    records = qr.fetchall()
    logging.debug('SQL: query result: %s' % str(records))

    for r in records:
        (_, enable, _) = r
        if enable == 1:
            logging.debug('Greylisting should be applied with record: %s' % str(r))
            return True

    return False


def restriction(**kwargs):
    # Bypass outgoing emails and mynetworks.
    if kwargs['smtp_session_data']['sasl_username']:
        logging.debug('Found SASL username, bypass greylisting.')
        return SMTP_ACTIONS['default']

    client_address = kwargs['smtp_session_data']['client_address']
    if client_address in settings.MYNETWORKS:
        logging.debug('Trusted/internal networks detected, bypass greylisting.')
        return SMTP_ACTIONS['default']

    conn = kwargs['conn_iredapd']

    if not conn:
        logging.error('No valid database connection.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']

    # TODO: add network of client address (e.g. xx.xx.xx/24)
    policy_senders = [sender,
                      '@' + sender_domain,
                      '@.' + sender_domain,
                      '@.',
                      client_address]

    if should_be_greylisted(conn=conn, senders=policy_senders):
        # Apply greylisting
        return action_greylisting

    return SMTP_ACTIONS['default']
