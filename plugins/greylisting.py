# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: greylisting.
# Reference: http://greylisting.org/

from libs.logger import logger
from libs import SMTP_ACTIONS, utils, ipaddress
from libs.utils import sqllist, is_trusted_client
import settings

# Return 4xx with greylisting message to Postfix.
action_greylisting = SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE


def _check_sender_type(sender):
    # Return string of sender type: email, ipv4, ipv6, cidr, domain, subdomain, catchall, unknown
    if sender == '@.':
        return 'catchall'

    if '@' in sender:
        if sender.startswith('@.'):
            if utils.is_domain(sender.lstrip('@.')):
                return 'subdomain'
        elif sender.startswith('@'):
            if utils.is_domain(sender.lstrip('@')):
                return 'domain'
        elif utils.is_email(sender):
            return 'email'
    elif '/' in sender:
        return 'cidr'
    elif utils.is_ipv4(sender):
        return 'ipv4'
    elif utils.is_ipv6(sender):
        return 'ipv6'

    return 'unknown'


def _is_whitelisted(conn, recipients, senders):
    """Check greylisting whitelists stored in table `greylisting_whitelists`,
    returns True if is whitelisted, otherwise returns False.

    conn        -- sql connection cursor
    recipient   -- full email address of recipient
    senders     -- list of senders we should check greylisting
    """

    # query whitelists based on recipient
    sql = """SELECT id, source
               FROM greylisting_whitelists
              WHERE account IN %s
              ORDER BY priority DESC""" % sqllist(senders)

    # check whitelisted senders
    # check whitelisted cidr
    return False


def _should_be_greylisted(conn, recipients, senders, client_address):
    """Check if greylisting should be applied to specified senders: True, False.

    conn -- sql connection cursor
    recipient -- full email address of recipient
    senders -- list of senders we should check greylisting
    """
    sql = """SELECT id, account, sender, sender_type, active
               FROM greylisting
              WHERE account IN %s
              ORDER BY priority DESC""" % sqllist(recipients)
    logger.debug('[SQL] query greylisting settings: \n%s' % sql)

    qr = conn.execute(sql)
    records = qr.fetchall()
    logger.debug('[SQL] query result: %s' % str(records))

    if not records:
        logger.debug('No setting found, greylisting is disabled for this client.')
        return False

    _ip = ipaddress.ip_address(unicode(client_address))

    for r in records:
        (_id, _account, _sender, _sender_type, _active) = r

        # Get valid sender_type
        if not _sender_type:
            _sender_type = _check_sender_type(_sender)

        _matched = False
        if _sender_type in ['email', 'ipv4', 'ipv6', 'domain', 'catchall', 'unknown']:
            # direct match
            if _sender in senders:
                _matched = True
        elif _sender_type in ['cidr']:
            _net = ()
            try:
                _net = ipaddress.ip_network(_sender)
                if _ip in _net:
                    _matched = True
            except Exception, e:
                logger.debug('Not an valid IP network: %s (error: %s)' % (_sender, str(e)))

        if _matched:
            if _active == 1:
                logger.debug('Greylisting should be applied due to SQL record: #%d, account=%s, sender=%s' % (_id, _account, _sender))
                return True
            else:
                logger.debug('Greylisting should NOT be applied due to SQL record: #%d, account=%s, sender=%s' % (_id, _account, _sender))
                return False

    # Turn off greylisting if no valid setting.
    logger.debug('No valid settings, fallback to turn off greylisting.')
    return False


def restriction(**kwargs):
    # Bypass outgoing emails.
    if kwargs['sasl_username']:
        logger.debug('Found SASL username, bypass greylisting for outbound email.')
        return SMTP_ACTIONS['default']

    client_address = kwargs['client_address']
    if is_trusted_client(client_address):
        return SMTP_ACTIONS['default']

    conn = kwargs['conn_iredapd']

    if not conn:
        logger.error('No valid database connection, fallback to default action.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    policy_recipients = [recipient, recipient_domain, '@.']
    policy_senders = [sender,
                      '@' + sender_domain,      # per-domain
                      '@.' + sender_domain,     # sub-domains
                      '@.',                     # catch-all
                      client_address]

    # Check greylisting whitelists
    if _is_whitelisted(conn, recipients=policy_recipients, senders=policy_senders):
        return SMTP_ACTIONS['default']

    # Check and apply greylisting settings
    if _should_be_greylisted(conn=conn,
                             recipients=policy_recipients,
                             senders=policy_senders,
                             client_address=client_address):
        # TODO check greylisting tracking.
        return action_greylisting

    return SMTP_ACTIONS['default']
