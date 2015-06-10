from sqlalchemy import create_engine
import settings

__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.7.0'

SMTP_ACTIONS = {
    'default': 'DUNNO',
    'accept': 'OK',
    # discard email without return error message to sender
    'discard': 'DISCARD Policy discard',
    # reject
    'reject': 'REJECT Policy rejection',
    # reject with reason
    'reject_blacklisted': 'REJECT Blacklisted',
    'reject_not_authorized': 'REJECT Not authorized',
    'reject_message_size_exceeded': 'REJECT Message size exceed (maybe caused by big attachment file)',
    'greylisting': '451 4.7.1',
}

# Mail list access policies.
# Unrestricted
MAILLIST_POLICY_PUBLIC = 'public'
# Only users under same domain are allowed
MAILLIST_POLICY_DOMAIN = 'domain'
# Only users under same domain and sub domains are allowed
MAILLIST_POLICY_SUBDOMAIN = 'subdomain'
# Only members are allowed
MAILLIST_POLICY_MEMBERSONLY = 'membersonly'
# Only moderators/allowed are allowed
MAILLIST_POLICY_ALLOWEDONLY = 'allowedonly'
# Only members and moderators are allowed
MAILLIST_POLICY_MEMBERSANDMODERATORSONLY = 'membersandmoderatorsonly'


# All the attributes that the Postfix SMTP server sends in a delegated SMTPD
# access policy request.
# Reference: http://www.postfix.org/SMTPD_POLICY_README.html
SMTP_SESSION_ATTRIBUTES = [
    # Postfix version 2.1 and later:
    'request',
    'protocol_state',
    'protocol_name',
    'helo_name',
    'queue_id',
    'sender',
    'recipient',
    'recipient_count',
    'client_address',
    'client_name',
    'reverse_client_name',
    'instance',
    # Postfix version 2.2 and later:
    'sasl_method',
    'sasl_username',
    'sasl_sender',
    'size',
    'ccert_subject',
    'ccert_issuer',
    'ccert_fingerprint',
    # Postfix version 2.3 and later:
    'encryption_protocol',
    'encryption_cipher',
    'encryption_keysize',
    'etrn_domain',
    # Postfix version 2.5 and later:
    'stress',
    # Postfix version 2.9 and later:
    'ccert_pubkey_fingerprint',
    # Postfix version 3.0 and later:
    'client_port',
]


def get_db_conn(dbn, db):
    try:
        uri = '%s://%s:%s@%s:%d/%s' % (dbn,
                                       settings.__dict__[db + '_db_user'],
                                       settings.__dict__[db + '_db_password'],
                                       settings.__dict__[db + '_db_server'],
                                       int(settings.__dict__[db + '_db_port']),
                                       settings.__dict__[db + '_db_name'])

        conn = create_engine(uri,
                             pool_size=20,
                             pool_recycle=3600,
                             max_overflow=0)
        return conn
    except:
        return None


def sqllist(values):
    """
        >>> _sqllist([1, 2, 3])
        <sql: '(1, 2, 3)'>
    """
    items = []
    items.append('(')
    for i, v in enumerate(values):
        if i != 0:
            items.append(', ')

        if isinstance(v, (int, long, float)):
            items.append("""%s""" % v)
        else:
            items.append("""'%s'""" % v)
    items.append(')')
    return ''.join(items)
