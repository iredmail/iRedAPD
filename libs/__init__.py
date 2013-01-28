__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.4.0'

SMTP_ACTIONS = {
    'default': 'DUNNO',
    'accept': 'OK',
    'reject': 'REJECT Not authorized',
}

MAILLIST_POLICY_PUBLIC = 'public'
MAILLIST_POLICY_DOMAIN = 'domain'
MAILLIST_POLICY_SUBDOMAIN = 'subdomain'
MAILLIST_POLICY_MEMBERSONLY = 'membersonly'
MAILLIST_POLICY_ALLOWEDONLY = 'allowedonly'      # Same as POLICY_MODERATORSONLY
MAILLIST_POLICY_MEMBERSANDMODERATORSONLY = 'membersandmoderatorsonly'

MAILLIST_ACCESS_POLICIES = {
    MAILLIST_POLICY_PUBLIC: 'Unrestricted',
    MAILLIST_POLICY_DOMAIN: 'Only users under same domain are allowed',
    MAILLIST_POLICY_SUBDOMAIN: 'Only users under same domain and sub domains are allowed',
    MAILLIST_POLICY_MEMBERSONLY: 'Only members are allowed',
    MAILLIST_POLICY_ALLOWEDONLY: 'Only moderators/allowed are allowed',
    MAILLIST_POLICY_MEMBERSANDMODERATORSONLY: 'Only members and moderators are allowed',
}
