# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Restrict who can send email to mail list.
# Note: Access policy is defined in libs/__init__.py.

import logging
from libs import SMTP_ACTIONS, LDAP_ACCESS_POLICIES_OF_MAIL_LIST
from libs.ldaplib import conn_utils

REQUIRE_LOCAL_SENDER = False
REQUIRE_LOCAL_RECIPIENT = True
SENDER_SEARCH_ATTRLIST = []
RECIPIENT_SEARCH_ATTRLIST = ['accessPolicy']


def restriction(**kwargs):
    smtp_session_data = kwargs['smtp_session_data']
    conn = kwargs['conn']
    base_dn = kwargs['base_dn']
    recipient_dn = kwargs['recipient_dn']
    recipient_ldif = kwargs['recipient_ldif']

    # Return if recipient is not a mail list object.
    if not 'mailList' in recipient_ldif['objectClass']:
        return 'DUNNO (Not mail list)'

    sender = smtp_session_data['sender'].lower()
    recipient = smtp_session_data['recipient'].lower()
    recipient_alias_domains = []

    policy = recipient_ldif.get('accessPolicy', ['public'])[0].lower()

    # Log access policy and description
    logging.debug('%s -> %s, access policy: %s (%s)' % (
        sender, recipient, policy,
        LDAP_ACCESS_POLICIES_OF_MAIL_LIST.get(policy, 'no description'))
    )

    if policy in ['domain', 'subdomain', ]:
        recipient_domain = recipient.split('@', 1)[-1]
        try:
            qr = conn.search_s(
                base_dn,
                1, # 1 == ldap.SCOPE_ONELEVEL
                "(&(objectClass=mailDomain)(|(domainName=%s)(domainAliasName=%s)))" % (recipient_domain, recipient_domain),
                ['domainName', 'domainAliasName', ]
            )
            if qr:
                dn, entries = qr[0]
                recipient_alias_domains = \
                        entries.get('domainName', []) + \
                        entries.get('domainAliasName', [])
        except Exception, e:
            logging.debug('Error while fetching alias domains: %s' % str(e))

        logging.debug('Recipient domain and alias domains: %s' % ','.join(recipient_alias_domains))

    # Verify access policy
    if policy == 'public':
        # No restriction.
        return 'DUNNO (Access policy: public)'
    elif policy == "domain":
        sender_domain = sender.split('@', 1)[-1]
        # Bypass all users under the same domain.
        if sender_domain in recipient_alias_domains:
            return 'DUNNO (Access policy: domain)'
        else:
            return SMTP_ACTIONS['reject']
    elif policy == "subdomain":
        # Bypass all users under the same domain and sub domains.
        returned = False
        for d in recipient_alias_domains:
            if sender.endswith(d) or sender.endswith('.' + d):
                return 'DUNNO (Access policy: subdomain (%s))' % (d)

        if returned is False:
            return SMTP_ACTIONS['reject']
    elif policy in ['membersonly', 'members',
                    'moderatorsonly', 'moderators',
                    'allowedonly', 'membersandmoderatorsonly']:
        # Handle other access policies: membersOnly, allowedOnly, membersAndModeratorsOnly.
        allowedSenders = conn_utils.get_allowed_senders_of_mail_list(
            conn=conn,
            base_dn=base_dn,
            dn_of_mail_list=recipient_dn,
            sender=sender,
            recipient=recipient,
            policy=policy,
        )

        if sender in allowedSenders:
            return 'DUNNO (Sender is allowed)'
        else:
            return SMTP_ACTIONS['reject']
    else:
        # Unknown access policy
        return SMTP_ACTIONS['default']
