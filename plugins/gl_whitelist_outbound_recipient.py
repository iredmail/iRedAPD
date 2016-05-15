"""Automatically disable greylisting for recipient in outgoing email for SASL
authenticated sender."""

from libs import SMTP_ACTIONS
from libs import greylisting as lib_gl
from libs.utils import is_email
from libs.logger import logger

def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']

    if not sasl_username:
        return SMTP_ACTIONS['default']

    recipient = kwargs['recipient']
    if not is_email(recipient):
        return SMTP_ACTIONS['default']

    conn_iredapd = kwargs['conn_iredapd']
    qr = lib_gl.disable_greylisting(conn=conn_iredapd,
                                    account=sasl_username,
                                    sender=recipient)

    if qr[0]:
        logger.debug('Address %s has been whitelisted for greylisting service for local user %s.' % (recipient, sasl_username))
    else:
        logger.error('<!> Error while whitelisting address %s for greylisting service for local user %s: %s' % (recipient, sasl_username, qr[1]))

    return SMTP_ACTIONS['default']
