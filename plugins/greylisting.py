# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: greylisting.

import logging
from libs import SMTP_ACTIONS
from libs.utils import sqllist, is_trusted_client
import settings

# Return 4xx with greylisting message to Postfix.
action_greylisting = SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE


def should_be_greylisted(conn, recipient, senders):
    """Check if greylisting should be applied to specified senders.

    conn - sql connection cursor
    recipient - full email address of recipient
    senders - list of senders we should check greylisting
    """
    # TODO check specified enable time. e.g. 9PM-6AM. (global, per-domain, per-user)
    # TODO check greylisting history of this client
    # TODO check whitelists (not same as whitelists used by plugin `amavisd_wblist`.
    sql = """SELECT sender, enable, priority FROM greylisting
             WHERE sender IN %s
             ORDER BY priority DESC""" % sqllist(senders)
    logging.debug('[SQL] query policy senders: \n%s' % sql)

    qr = conn.execute(sql)
    records = qr.fetchall()
    logging.debug('[SQL] query result: %s' % str(records))

    for r in records:
        (_, enable, _) = r
        if enable == 1:
            logging.debug('Greylisting should be applied due to SQL record: %s' % str(r))
            return True

    return False


def restriction(**kwargs):
    # Bypass outgoing emails.
    if kwargs['smtp_session_data']['sasl_username']:
        logging.debug('Found SASL username, bypass greylisting.')
        return SMTP_ACTIONS['default']

    client_address = kwargs['smtp_session_data']['client_address']
    if is_trusted_client(client_address):
        return SMTP_ACTIONS['default']

    conn = kwargs['conn_iredapd']

    if not conn:
        logging.error('No valid database connection, fallback to default action.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']

    # TODO: add network of client address (e.g. xx.xx.xx/24)
    policy_senders = [sender,
                      '@' + sender_domain,      # per-domain
                      '@.' + sender_domain,     # sub-domains
                      '@.',                     # catch-all
                      client_address]

    if should_be_greylisted(conn=conn, recipient=recipient, senders=policy_senders):
        # TODO check time period

        # Apply greylisting
        return action_greylisting

    return SMTP_ACTIONS['default']
