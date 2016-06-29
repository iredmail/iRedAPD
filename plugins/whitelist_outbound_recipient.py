# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Automatically whitelist recipient or recipient domain for
#          greylisting service.

from libs import SMTP_ACTIONS
from libs import greylisting as lib_gl
from libs.utils import is_email
from libs.logger import logger

import settings

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import is_local_domain
else:
    from libs.sql import is_local_domain

SMTP_PROTOCOL_STATE = ['END-OF-MESSAGE']


def restriction(**kwargs):
    if not (settings.WL_RCPT_FOR_GREYLISTING or settings.WL_RCPT_WITHOUT_SPF):
        logger.debug('No setting available: WL_RCPT_FOR_GREYLISTING, WL_RCPT_WITHOUT_SPF. Skip.')
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

    conn_iredapd = kwargs['conn_iredapd']

    # Submit recipient as whitelisted sender directly
    if settings.WL_RCPT_WITHOUT_SPF:
        if settings.WL_RCPT_LOCAL_ACCOUNT == 'user':
            _wl_account = sasl_username
        elif settings.WL_RCPT_LOCAL_ACCOUNT == 'domain':
            _wl_account = sasl_username_domain
        else:
            _wl_account = '@.'

        if settings.WL_RCPT_RCPT == 'domain':
            _wl_sender = recipient_domain
        else:
            _wl_sender = recipient

        qr = lib_gl.add_whitelist_sender(conn=conn_iredapd,
                                         account=_wl_account,
                                         sender=_wl_sender)

        if qr[0]:
            logger.info('Recipient %s has been whitelisted for %s.' % (_wl_sender, _wl_account))
        else:
            logger.error('<!> Error while whitelisting recipient %s for %s: %s' % (_wl_sender, _wl_account, qr[1]))

    if settings.WL_RCPT_FOR_GREYLISTING:
        if settings.WL_RCPT_WHITELIST_DOMAIN_FOR_GREYLISTING:
            # Whitelist recipient domain for greylisting
            qr = lib_gl.add_whitelist_domain(conn=conn_iredapd,
                                             domain=recipient_domain)

            if qr[0]:
                logger.info('Domain %s has been whitelisted globally for greylisting service.' % recipient_domain)
            else:
                logger.error('<!> Error while whitelisting domain %s globally for greylisting service: %s' % (recipient_domain, qr[1]))
        else:
            # Whitelist recipient for greylisting
            qr = lib_gl.add_whitelist_sender(conn=conn_iredapd,
                                             account=sasl_username,
                                             sender=recipient,
                                             comment='AUTO-WHITELISTED')

            if qr[0]:
                logger.info('Address %s has been whitelisted for greylisting service for local user %s.' % (recipient, sasl_username))
            else:
                logger.error('<!> Error while whitelisting address %s for greylisting service for local user %s: %s' % (recipient, sasl_username, qr[1]))

    return SMTP_ACTIONS['default']
