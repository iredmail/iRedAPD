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
    smtpSessionData = kwargs['smtpSessionData']
    ldapConn = kwargs['conn']
    ldapBaseDn = kwargs['baseDn']
    ldapRecipientDn = kwargs['recipientDn']
    ldapRecipientLdif = kwargs['recipientLdif']

    # Return if recipient is not a mail list object.
    if 'maillist' not in [v.lower() for v in ldapRecipientLdif['objectClass']]:
        return 'DUNNO (Not mail list)'

    sender = smtpSessionData['sender'].lower()
    sender_domain = sender.split('@')[-1]

    recipient = smtpSessionData['recipient'].lower()
    recipient_domain = recipient.split('@')[-1]
    recipient_alias_domains = []

    policy = ldapRecipientLdif.get('accessPolicy', ['public'])[0].lower()

    if policy in ['domain', 'subdomain',]:
        try:
            qr = ldapConn.search_s(
                ldapBaseDn,
                1, # 1 == ldap.SCOPE_ONELEVEL
                "(&(objectClass=mailDomain)(|(domainName=%s)(domainAliasName=%s)))" % (recipient_domain, recipient_domain),
                ['domainName', 'domainAliasName',]
            )
            if len(qr) > 0:
                recipient_alias_domains = qr[0][1].get('domainName', []) + qr[0][1].get('domainAliasName', [])
        except Exception, e:
            logging.debug('Error while fetch domainAliasName: %s' % str(e))

        logging.debug('Recipient domain and alias domains: %s' % ','.join(recipient_alias_domains))

    logging.debug('%s -> %s, access policy: %s (%s)' % (
        sender, recipient, policy,
        LDAP_ACCESS_POLICIES_OF_MAIL_LIST.get(policy, 'no description'))
    )

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
            if sender.endswith(d) or sender.endswith('.' + d):
                return 'DUNNO (Access policy: subdomain (%s))' % (d)

        if returned is False:
            return SMTP_ACTIONS['reject']
    else:
        # Handle other access policies: membersOnly, allowedOnly, membersAndModeratorsOnly.
        allowedSenders = conn_utils.get_allowed_senders_of_mail_list(
            conn=ldapConn,
            base_dn=ldapBaseDn,
            dn_of_mail_list=ldapRecipientDn,
            sender=sender,
            recipient=recipient,
            policy=policy,
        )

        if sender.lower() in [v.lower() for v in allowedSenders]:
            return 'DUNNO (Sender is allowed)'
        else:
            return SMTP_ACTIONS['reject']
