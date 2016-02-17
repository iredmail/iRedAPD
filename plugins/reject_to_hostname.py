# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Reject emails sent to xxx@[your_server_hostname].

import socket

from libs.utils import is_trusted_client

server_hostname = socket.gethostname()

def restriction(*args, **kwargs):
    # Bypass authenticated user.
    if kwargs['sasl_username']:
        return 'DUNNO'

    # Bypass localhost.
    if is_trusted_client(kwargs['client_address']):
        return 'DUNNO'

    rcpt_domain = kwargs['recipient_domain']
    if rcpt_domain == server_hostname:
        return 'REJECT Not authorized'

    return 'DUNNO'
