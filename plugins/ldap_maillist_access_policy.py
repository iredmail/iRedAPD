# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Restrict who can send email to mail list.
# Note: Access policy is defined in libs/__init__.py.

import logging
from libs import SMTP_ACTIONS
from libs.ldaplib import conn_utils

REQUIRE_LOCAL_SENDER = False
REQUIRE_LOCAL_RECIPIENT = True
SENDER_SEARCH_ATTRLIST = []
RECIPIENT_SEARCH_ATTRLIST = ['listAllowedUser', 'accessPolicy']

# Target smtp protocol state.
SMTP_PROTOCOL_STATE = 'RCPT'


def restriction(**kwargs):
    recipient_ldif = kwargs['recipient_ldif']

    # Return if recipient is not a mail list object.
    if not recipient_ldif:
        return 'DUNNO (No recipient LDIF data)'

    if not 'mailList' in recipient_ldif.get('objectClass', []):
        return 'DUNNO (Not a mail list account)'

    conn = kwargs['conn']
    base_dn = kwargs['base_dn']
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_dn = kwargs['recipient_dn']

    recipient_alias_domains = []
    policy = recipient_ldif.get('accessPolicy', ['public'])[0].lower()

    # Log access policy and description
    logging.debug('%s -> %s, access policy: %s' % (sender, recipient, policy))

    if policy in ['domain', 'subdomain', ]:
        recipient_domain = recipient.split('@', 1)[-1]
        try:
            qr = conn.search_s(
                base_dn,
                1,  # 1 == ldap.SCOPE_ONELEVEL
                "(&(objectClass=mailDomain)(|(domainName=%s)(domainAliasName=%s)))" % (recipient_domain, recipient_domain),
                ['domainName', 'domainAliasName', ],
            )
            if qr:
                dn, entries = qr[0]
                recipient_alias_domains = entries.get('domainName', []) + entries.get('domainAliasName', [])
        except Exception, e:
            logging.debug('Error while fetching alias domains: %s' % str(e))

        logging.debug('Recipient domain and alias domains: %s' % ','.join(recipient_alias_domains))

    # Verify access policy
    if policy == 'public':
        # No restriction.
        return 'DUNNO (Access policy: public)'
    elif policy == "domain":
        # Bypass all users under the same domain.
        if sender_domain in recipient_alias_domains:
            return 'DUNNO (Access policy: domain)'
        else:
            return SMTP_ACTIONS['reject']
    elif policy == "subdomain":
        # Bypass all users under the same domain and sub domains.
        returned = False
        for d in recipient_alias_domains:
            if sender.endswith('@' + d) or sender.endswith('.' + d):
                return 'DUNNO (Access policy: subdomain (%s))' % (d)

        if returned is False:
            return SMTP_ACTIONS['reject']
    elif policy in ['membersonly', 'allowedonly', 'membersandmoderatorsonly']:
        allowed_senders = recipient_ldif.get('listAllowedUser', [])
        if policy == 'allowedonly':
            if sender in allowed_senders or sender_domain in allowed_senders:
                return 'DUNNO (Allowed explicitly)'
            logging.debug('Sender is not explicitly allowed, query user aliases and alias domains.')

        allowedSenders = conn_utils.get_allowed_senders_of_mail_list(
            conn=conn,
            dn_of_mail_list=recipient_dn,
            sender=sender,
            recipient=recipient,
            policy=policy,
            allowed_senders=allowed_senders,
        )

        if policy == 'allowedonly':
            # Check allowed sender domain or sub-domains
            sender_domain = kwargs['sender_domain']
            all_possible_sender_domains = [sender_domain]
            domain_parts = sender_domain.split('.')
            for i in range(len(domain_parts)):
                all_possible_sender_domains += ['.' + '.'.join(domain_parts)]
                domain_parts.pop(0)

            logging.debug('All possible sender domains: %s' % ', '.join(all_possible_sender_domains))
            if set(all_possible_sender_domains) & set(allowedSenders):
                return 'DUNNO (Sender domain or its sub-domain is allowed)'

        if sender in allowedSenders:
            return 'DUNNO (Sender is allowed)'
        else:
            return SMTP_ACTIONS['reject']
    else:
        # Unknown access policy
        return SMTP_ACTIONS['default']
