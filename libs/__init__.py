__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.4.4'

SMTP_ACTIONS = {
    'default': 'DUNNO',
    'accept': 'OK',
    'reject': 'REJECT',
    # Define actions with custom reason.
    'reject_not_authorized': 'REJECT Not authoried',
    'reject_message_size_exceeded': 'REJECT Message size exceed (maybe caused by big attachment file)',
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
