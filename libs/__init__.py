__author__ = "Zhang Huangbin <zhb@iredmail.org>"
__version__ = "5.9.3"


SMTP_ACTIONS = {
    'default': 'DUNNO',
    # Use 'OK' carefully, it will bypass other Postfix/iRedAPD restrictions.
    'whitelist': 'OK',
    # discard email without return error message to sender
    'discard': 'DISCARD Policy discard',
    # reject
    'reject': 'REJECT Policy rejection',
    # reject with reason
    'reject_null_sender': 'REJECT Policy rejection due to null sender',
    'reject_forged_sender': 'REJECT SMTP AUTH is required for users under this sender domain',
    'reject_sender_login_mismatch': 'REJECT Sender is not same as SMTP authenticate username',
    'reject_blacklisted': 'REJECT Blacklisted',
    'reject_not_authorized': 'REJECT Not authorized',
    'reject_message_size_exceeded': 'REJECT Message size exceed (maybe caused by big attachment file)',
    'reject_blacklisted_rdns': 'REJECT Blacklisted reverse DNS name of server IP address',
    # Throttling
    'reject_quota_exceeded': 'REJECT Throttling quota exceeded',
    'reject_msg_size_exceeded': 'REJECT Message size is too large',
    'reject_max_rcpts_exceeded': 'REJECT Too many recipients in single message',
    # Sender Score
    'reject_low_sender_score': 'REJECT Server IP address has bad reputation. FYI: https://www.senderscore.org/lookup.php?lookup=',
    'greylisting': '451 4.7.1',
}

# Default replies for Postfix tcp table.
# Reference: http://www.postfix.org/tcp_table.5.html
TCP_REPLIES = {
    # In case of a lookup request, the requested data does not exist.
    # In case of an update request, the request was rejected. The text
    # describes the nature of the problem.
    'not_exist': '500 ',

    # This indicates an error condition. The text describes the nature
    # of the problem. The client should retry the request later.
    'error': '400 Error ',

    # The request was successful. In the case of a lookup request,
    # the text contains an encoded version of the requested data.
    'success': '200 ',
}

# Plugin priorities.
#
# * With pre-defined priorities, the order defined in `plugins = []` setting
#   doesn't matter at all, so that we can apply plugins in ideal order.
#
# * It's better to run plugins which doesn't require SQL/LDAP connection first.
#               +-----------------------------------+
# * Plugin with | larger number has higher priority | and will be applied first.
#               +-----------------------------------+
PLUGIN_PRIORITIES = {
    'reject_null_sender': 100,
    'reject_to_hostname': 100,
    'wblist_rdns': 99,
    'reject_sender_login_mismatch': 90,
    'greylisting': 80,
    'ldap_force_change_password_in_days': 70,
    'sql_force_change_password_in_days': 70,
    'throttle': 60,
    'ldap_maillist_access_policy': 50,
    'sql_ml_access_policy': 51,
    'sql_alias_access_policy': 50,
    'amavisd_wblist': 40,
    'whitelist_outbound_recipient': 30,
    'senderscore': 10,
}

# Account proiroties.
# Used in plugins:
#   - greylisting.py
ACCOUNT_PRIORITIES = {
    'email': 100,               # e.g. 'user@domain.com'. Highest priority
    'wildcard_addr': 90,        # e.g. `user@*`. used in plugin `amavisd_wblist`
                                # as wildcard sender. e.g. 'user@*`
    'ip': 80,                   # e.g. 173.254.22.21
    'wildcard_ip': 70,          # e.g. 173.254.22.*
    'cidr': 70,                 # e.g. 173.254.22.0/24
    'domain': 60,               # e.g. @domain.com
    'subdomain': 50,            # e.g. @.domain.com
    'top_level_domain': 40,     # e.g. @com, @org
    'catchall': 0,              # '@.'. Lowest priority
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
MAILLIST_POLICY_MODERATORS = 'moderatorsonly'
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
    # Postfix version 3.1 and later:
    'policy_context',
    # Postfix version 3.2 and later:
    'server_address',
    'server_port',
    # Postfix version 3.8 and later:
    'compatibility_level',
    'mail_version',
]
