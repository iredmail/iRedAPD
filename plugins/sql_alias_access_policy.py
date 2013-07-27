# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Apply access policy on sender while recipient is an mail alias.

# Available access policies:
#   - public:   Unrestricted
#   - domain:   Only users under same domain are allowed.
#   - subdomain:    Only users under same domain and sub domains are allowed.
#   - membersOnly:  Only members are allowed.
#   - moderatorsOnly:   Only moderators are allowed.
#   - membersAndModeratorsOnly: Only members and moderators are allowed.

import logging
from libs import SMTP_ACTIONS
from libs import MAILLIST_POLICY_PUBLIC
from libs import MAILLIST_POLICY_DOMAIN
from libs import MAILLIST_POLICY_SUBDOMAIN
from libs import MAILLIST_POLICY_MEMBERSONLY
from libs import MAILLIST_POLICY_ALLOWEDONLY
from libs import MAILLIST_POLICY_MEMBERSANDMODERATORSONLY


def restriction(**kwargs):
    conn = kwargs['conn']
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    sql = '''SELECT accesspolicy, goto, moderators
            FROM alias
            WHERE
                address='%s'
                AND address <> goto
                AND domain='%s'
                AND active=1
            LIMIT 1
    ''' % (recipient, recipient_domain)
    logging.debug('SQL: %s' % sql)

    conn.execute(sql)
    sql_record = conn.fetchone()
    logging.debug('SQL Record: %s' % str(sql_record))

    # Recipient account doesn't exist.
    if sql_record is None:
        return 'DUNNO (Not mail alias)'

    policy = str(sql_record[0]).lower()

    # Log access policy and description
    logging.debug('%s -> %s, access policy: %s' % (sender, recipient, policy))

    members = [str(v.lower()) for v in str(sql_record[1]).split(',')]
    moderators = [str(v.lower()) for v in str(sql_record[2]).split(',')]

    logging.debug('policy: %s' % policy)
    logging.debug('members: %s' % ', '.join(members))
    logging.debug('moderators: %s' % ', '.join(moderators))

    if not len(policy) > 0:
        return 'DUNNO (No access policy)'

    if policy == MAILLIST_POLICY_PUBLIC:
        # Return if no access policy available or policy is @POLICY_PUBLIC.
        return 'DUNNO'
    elif policy == MAILLIST_POLICY_DOMAIN:
        # Bypass all users under the same domain.
        if sender_domain == recipient_domain:
            return 'DUNNO'
        else:
            return SMTP_ACTIONS['reject']
    elif policy == MAILLIST_POLICY_SUBDOMAIN:
        # Bypass all users under the same domain or sub domains.
        if sender.endswith(recipient_domain) or sender.endswith('.' + recipient_domain):
            return 'DUNNO'
        else:
            return SMTP_ACTIONS['reject']
    elif policy == MAILLIST_POLICY_MEMBERSONLY:
        # Bypass all members.
        if sender in members:
            return 'DUNNO'
        else:
            return SMTP_ACTIONS['reject']
    elif policy == MAILLIST_POLICY_ALLOWEDONLY:
        # Bypass all moderators.
        if sender in moderators:
            return 'DUNNO'
        else:
            return SMTP_ACTIONS['reject']
    elif policy == MAILLIST_POLICY_MEMBERSANDMODERATORSONLY:
        # Bypass both members and moderators.
        if sender in members or sender in moderators:
            return 'DUNNO'
        else:
            return SMTP_ACTIONS['reject']
    else:
        # Bypass all if policy is not defined in this plugin.
        return 'DUNNO (Policy is not defined: %s)' % policy
