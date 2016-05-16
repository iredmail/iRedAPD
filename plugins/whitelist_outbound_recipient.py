"""Automatically disable greylisting for recipient in outgoing email for SASL
authenticated sender."""

from libs import SMTP_ACTIONS
from libs import greylisting as lib_gl
from libs import wblist
from libs.utils import is_email
from libs.logger import logger

import settings

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import is_local_domain
else:
    from libs.sql import is_local_domain

SMTP_PROTOCOL_STATE = ['END-OF-MESSAGE']

wl_greylisting = settings.WL_RCPT_UPDATE_GREYLISTING
wl_whitelist = settings.WL_RCPT_UPDATE_WHITELIST

def restriction(**kwargs):
    if not (wl_greylisting or wl_whitelist):
        logger.debug('No setting available: WL_RCPT_UPDATE_GREYLISTING, WL_RCPT_UPDATE_WHITELIST.')
        return SMTP_ACTIONS['default']

    sasl_username = kwargs['sasl_username']

    if not sasl_username:
        logger.debug('No sasl_username found, skip.')
        return SMTP_ACTIONS['default']

    recipient = kwargs['recipient']
    if not is_email(recipient):
        logger.debug('Recipient is not a valid email address, skip.')
        return SMTP_ACTIONS['default']

    # Check whether recipient domain is hosted locally.
    sasl_username_domain = kwargs['sasl_username_domain']
    recipient_domain = kwargs['recipient_domain']

    if sasl_username_domain == recipient_domain:
        logger.debug('Sender domain is same as recipient domain, skip.')
        return SMTP_ACTIONS['default']

    conn_vmail = kwargs['conn_vmail']
    if is_local_domain(conn=conn_vmail, domain=recipient_domain):
        logger.debug('Recipient domain is local domain, skip.')
        return SMTP_ACTIONS['default']

    if wl_greylisting:
        conn_iredapd = kwargs['conn_iredapd']
        qr = lib_gl.add_whitelist_sender(conn=conn_iredapd,
                                         account=sasl_username,
                                         sender=recipient,
                                         comment='AUTO-WHITELISTED')

        if qr[0]:
            logger.debug('Address %s has been whitelisted for greylisting service for local user %s.' % (recipient, sasl_username))
        else:
            logger.error('<!> Error while whitelisting address %s for greylisting service for local user %s: %s' % (recipient, sasl_username, qr[1]))

    if wl_whitelist:
        conn_amavisd = kwargs['conn_amavisd']
        qr = wblist.add_wblist(conn=conn_amavisd,
                               account=sasl_username,
                               wl_senders=[recipient])

        if qr[0]:
            logger.debug('Address %s has been whitelisted for local user %s.' % (recipient, sasl_username))
        else:
            logger.error('<!> Error while whitelisting address %s for local user %s: %s' % (recipient, sasl_username, qr[1]))

    return SMTP_ACTIONS['default']
