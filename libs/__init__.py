__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.7.0'

# Plugin priorities.
#
# With pre-defined priorities, the order defined in `plugins = []` setting
# doesn't matter at all, so that we can apply plugins in ideal order.
#
# Plugin with smaller number has higher priority and will be applied first.
PLUGIN_PRIORITIES = {'reject_null_sender': 10,
                     'greylisting': 20,
                     'reject_sender_login_mismatch': 30,
                     'ldap_force_change_password_in_days': 40,
                     'sql_force_change_password_in_days': 50,
                     'throttle': 60,
                     'amavisd_wblist': 70,
                     'ldap_maillist_access_policy': 80,
                     'sql_alias_access_policy': 90}

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
    # Throttling
    'reject_exceed_msg_size': 'REJECT Quota exceeded (size of single mail message)',
    'reject_exceed_max_msgs': 'REJECT Quota exceeded (number of mails in total)',
    'reject_exceed_max_quota': 'REJECT Quota exceeded (accumulated message size)',
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
    'queue_id',             # Empty in RCPT state
    'sender',
    'recipient',
    'recipient_count',      # Empty in RCPT state
    'client_address',
    'client_name',
    'reverse_client_name',
    'instance',
    # Postfix version 2.2 and later:
    'sasl_method',
    'sasl_username',
    'sasl_sender',
    'size',                 # Empty in RCPT
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
