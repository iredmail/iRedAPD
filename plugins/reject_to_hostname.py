# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Reject emails sent to xxx@[your_server_hostname].

import socket

from libs import SMTP_ACTIONS
from libs.utils import is_trusted_client

server_hostname = socket.gethostname()

def restriction(*args, **kwargs):
    # Bypass authenticated user.
    if kwargs['sasl_username']:
        return SMTP_ACTIONS['default']

    # Bypass localhost.
    if is_trusted_client(kwargs['client_address']):
        return SMTP_ACTIONS['default']

    recipient = kwargs['recipient']
    rcpt_domain = kwargs['recipient_domain']
    if (rcpt_domain == server_hostname) and (not r:
        return SMTP_ACTIONS['reject_not_authorized']

    return SMTP_ACTIONS['default']
