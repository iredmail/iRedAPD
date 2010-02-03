#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <michaelbibby (at) gmail.com>

import sys

ACTION_REJECT = 'REJECT Not Authorized'

def __get_allowed_senders(ldapConn, ldapBaseDn, listDn, sender, recipient, policy,):
    """return search_result_list_based_on_access_policy"""

    # Set search base dn, scope, filter and attribute list based on access policy.
    if policy == 'membersonly':
        basedn = ldapBaseDn
        searchScope = 2     # ldap.SCOPE_SUBTREE
        # Filter used to get domain members.
        searchFilter = "(&(objectclass=mailUser)(accountStatus=active)(memberOfGroup=%s))" % (recipient, )
        searchAttr = 'mail'
    else:
        basedn = listDn
        searchScope = 0     # Use SCOPE_BASE to improve performance.
        # Filter used to get domain moderators.
        searchFilter = "(&(objectclass=mailList)(mail=%s))" % (recipient, )
        searchAttr = 'listAllowedUser'

    try:
        result = ldapConn.search_s(basedn, searchScope, searchFilter, [searchAttr])
        if result[0][1].has_key(searchAttr):
            # Example of result data:
            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
            return result[0][1][searchAttr]
        else:
            return []

    except Exception, e:
        return []

def restriction(ldapConn, ldapBaseDn, ldapRecipientDn, ldapRecipientLdif, smtpSessionData, **kargs):
    # Return if recipient is not a mail list object.
    if 'maillist' not in [ v.lower() for v in ldapRecipientLdif['objectClass']]:
        return 'DUNNO'

    sender = smtpSessionData['sender'].lower()
    recipient = smtpSessionData['recipient'].lower()
    policy = ldapRecipientLdif.get('accessPolicy', ['public'])[0].lower()

    if policy == "public": return 'DUNNO'   # No restriction.
    elif policy == "domain":
        # Bypass all users under the same domain.
        if sender.split('@')[1] == recipient.split('@')[1]: return 'DUNNO'
        else: return ACTION_REJECT
    else:
        # Handle other access policies: membersOnly, allowedOnly.
        allowedSenders = __get_allowed_senders(
                ldapConn=ldapConn,
                ldapBaseDn=ldapBaseDn,
                listDn=ldapRecipientDn,
                sender=sender,
                recipient=recipient,
                policy=policy,
                )

        if sender.lower() in [ v.lower for v in allowedSenders ]:
            return 'DUNNO'
        else:
            return ACTION_REJECT
