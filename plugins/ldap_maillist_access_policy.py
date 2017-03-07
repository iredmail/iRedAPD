# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Restrict who can send email to mail list.
# Note: Available access policy names are defined in file `libs/__init__.py`.

from libs.logger import logger
from libs import SMTP_ACTIONS
from libs.ldaplib import conn_utils

REQUIRE_LOCAL_RECIPIENT = True
RECIPIENT_SEARCH_ATTRLIST = ['listAllowedUser', 'accessPolicy']


def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']
    recipient = kwargs['recipient']
    recipient_ldif = kwargs['recipient_ldif']

    if sasl_username == recipient:
        return SMTP_ACTIONS['default'] + ' (sasl_username == recipient, not a mail list account)'

    # Return if recipient is not a mail list object.
    if not recipient_ldif:
        return SMTP_ACTIONS['default'] + ' (No recipient LDIF data)'

    if 'mailList' not in recipient_ldif['objectClass']:
        return SMTP_ACTIONS['default'] + ' (Recipient is not a mailing list account)'

    # Get access policy
    policy = recipient_ldif.get('accessPolicy', ['public'])[0].lower()

    # Log access policy
    logger.debug('Access policy of mailing list (%s): %s' % (recipient, policy))
    if policy == 'public':
        return SMTP_ACTIONS['default'] + ' (Access policy: public, no restriction)'

    conn = kwargs['conn_vmail']
    base_dn = kwargs['base_dn']
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient_domain = kwargs['recipient_domain']

    # Primary recipient domain and all its alias domains
    valid_rcpt_domains = []

    if policy in ['domain', 'subdomain']:
        try:
            _f = "(&(objectClass=mailDomain)(|(domainName=%s)(domainAliasName=%s)))" % (recipient_domain, recipient_domain)
            qr = conn.search_s(base_dn,
                               1,  # 1 == ldap.SCOPE_ONELEVEL
                               _f,
                               ['domainName', 'domainAliasName'])
            if qr:
                dn, entries = qr[0]
                valid_rcpt_domains = entries.get('domainName', []) + entries.get('domainAliasName', [])
                logger.debug('Recipient domain and all alias domains: %s' % ','.join(valid_rcpt_domains))
        except Exception, e:
            # Log and return if LDAP error occurs
            logger.error('Error while fetching alias domains of recipient domain %s: %s' % (recipient_domain, repr(e)))
            return SMTP_ACTIONS['default'] + ' (Error while fetching alias domains of recipient domain %s: %s' % (recipient_domain, repr(e))

    # Verify access policy
    if policy == "domain":
        # Bypass all users under the same domain.
        if sender_domain in valid_rcpt_domains:
            return SMTP_ACTIONS['default'] + ' (Sender bypasses access policy: domain (%s))' % (sender_domain)

        return SMTP_ACTIONS['reject_not_authorized']
    elif policy == "subdomain":
        # Bypass all users under the same domain and sub domains.
        for d in valid_rcpt_domains:
            if sender_domain == d or sender_domain.endswith('.' + d):
                return SMTP_ACTIONS['default'] + ' (Sender bypasses access policy: subdomain (%s))' % (d)

        return SMTP_ACTIONS['reject_not_authorized']
    elif policy in ['membersonly',
                    'allowedonly',
                    'moderatorsonly',
                    'membersandmoderatorsonly']:
        explicitly_allowed_senders = recipient_ldif.get('listAllowedUser', [])
        if policy in ['allowedonly', 'moderatorsonly']:
            if sender in explicitly_allowed_senders:
                return SMTP_ACTIONS['default'] + '  (Sender is allowed explicitly: %s)' % sender
            elif sender_domain in explicitly_allowed_senders or '*@' + sender_domain in explicitly_allowed_senders:
                return SMTP_ACTIONS['default'] + '  (Sender domain is allowed explicitly: %s)' % sender_domain

            logger.debug('Sender is not explicitly allowed, query user aliases and alias domains.')

        # Remove '*@domain.com'
        qr_allowed_senders = [s for s in explicitly_allowed_senders if not s.startswith('*@')]
        allowed_senders = conn_utils.get_allowed_senders_of_mail_list(
            conn=conn,
            sender=sender,
            recipient=recipient,
            recipient_domain=recipient_domain,
            policy=policy,
            allowed_senders=qr_allowed_senders,
        )

        if policy in ['allowedonly', 'moderatorsonly']:
            # Check allowed sender domain or sub-domains
            all_possible_sender_domains = [sender_domain]
            _domain_parts = sender_domain.split('.')
            for i in _domain_parts:
                all_possible_sender_domains += ['.' + '.'.join(_domain_parts)]
                _domain_parts.pop(0)

            logger.debug('Possible sender domains: %s' % ', '.join(all_possible_sender_domains))
            if set(all_possible_sender_domains) & set(allowed_senders):
                return SMTP_ACTIONS['default'] + ' (Sender domain or its sub-domain is allowed)'

        if sender in allowed_senders:
            return SMTP_ACTIONS['default'] + ' (Sender is allowed)'
        else:
            return SMTP_ACTIONS['reject_not_authorized']
    else:
        # Unknown access policy
        return SMTP_ACTIONS['default']
