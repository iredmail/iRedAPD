#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <michaelbibby (at) gmail.com>

# ----------------------------------------------------------------------------
# This plugin is used for mail deliver restriction.
#
# Handled policies:
#   - public:   Unrestricted
#   - domain:   Only users under same domain are allowed.
#   - subdomain:    Only users under same domain and sub domains are allowed.
#   - membersOnly:  Only members are allowed.
#   - moderatorsOnly:   Only moderators are allowed.
#   - membersAndModeratorsOnly: Only members and moderators are allowed.

# ----------------------------------------------------------------------------

import sys
import os

ACTION_REJECT = 'REJECT Not Authorized.'
PLUGIN_NAME = os.path.basename(__file__)

def __get_allowed_senders(ldapConn, ldapBaseDn, listDn, sender, recipient, policy, logger, *kw, **kargs):
    """return search_result_list_based_on_access_policy"""

    logger.debug('(%s) Get allowed senders...' % (PLUGIN_NAME))

    recipient_domain = recipient.split('@', 1)[-1]

    # Set base dn as domain dn.
    domaindn = 'domainName=' + recipient_domain + ',' + ldapBaseDn

    # Default search scope. 2==ldap.SCOPE_SUBTREE
    searchScope = 2

    # Set search filter, attributes based on policy.
    # Override base dn, scope if necessary.
    if policy == 'membersonly':
        basedn = domaindn
        # Filter: get mail list members.
        searchFilter = "(&(|(objectclass=mailUser)(objectClass=mailExternalUser))(accountStatus=active)(memberOfGroup=%s))" % (recipient, )

        # Get both mail and shadowAddress.
        searchAttrs = ['mail', 'shadowAddress',]

    elif policy == 'allowedonly' or policy == 'moderatorsonly':
        # Get mail list moderators.
        basedn = listDn
        searchScope = 0     # Use ldap.SCOPE_BASE to improve performance.
        searchFilter = "(&(objectclass=mailList)(mail=%s))" % (recipient, )
        searchAttrs = ['listAllowedUser']

    else:
        basedn = domaindn
        # Policy: policy==membersAndModeratorsOnly or not set.
        # Filter used to get both members and moderators.
        searchFilter = "(|(&(|(objectClass=mailUser)(objectClass=mailExternalUser))(memberOfGroup=%s))(&(objectclass=mailList)(mail=%s)))" % (recipient, recipient, )
        searchAttrs = ['mail', 'shadowAddress', 'listAllowedUser',]

    logger.debug('(%s) base dn: %s' % (PLUGIN_NAME, basedn))
    logger.debug('(%s) search scope: %s' % (PLUGIN_NAME, searchScope))
    logger.debug('(%s) search filter: %s' % (PLUGIN_NAME, searchFilter))
    logger.debug('(%s) search attributes: %s' % (PLUGIN_NAME, ', '.join(searchAttrs)))

    try:
        result = ldapConn.search_s(basedn, searchScope, searchFilter, searchAttrs)
        userList = []
        for obj in result:
            for k in searchAttrs:
                if k in obj[1].keys():
                    # Example of result data:
                    # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
                    userList += obj[1][k]
                else:
                    pass

        # Exclude mail list itself.
        if recipient in userList:
            userList.remove(recipient)

        logger.debug('(%s) search result: %s' % (PLUGIN_NAME, str(userList)))

        # Query once more to get 'shadowAddress'.
        if len(userList) > 0 and (policy == 'allowedonly' or policy == 'moderatorsonly'):
            logger.debug('(%s) Addition query to get user aliases...' % (PLUGIN_NAME))

            basedn = 'ou=Users,' + domaindn
            searchFilter = '(&(objectClass=mailUser)(enabledService=shadowaddress)(|'
            for i in userList:
                searchFilter += '(mail=%s)' % i
            searchFilter += '))'

            searchAttrs = ['shadowAddress',]

            logger.debug('(%s) base dn: %s' % (PLUGIN_NAME, basedn))
            logger.debug('(%s) search scope: 2 (ldap.SCOPE_SUBTREE)' % (PLUGIN_NAME))
            logger.debug('(%s) search filter: %s' % (PLUGIN_NAME, searchFilter))
            logger.debug('(%s) search attributes: %s' % (PLUGIN_NAME, ', '.join(searchAttrs)))

            try:
                resultOfShadowAddresses = ldapConn.search_s(
                    'ou=Users,'+domaindn,
                    2,  # ldap.SCOPE_SUBTREE
                    searchFilter,
                    ['mail', 'shadowAddress',],
                )

                for obj in resultOfShadowAddresses:
                    for k in searchAttrs:
                        if k in obj[1].keys():
                            # Example of result data:
                            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
                            userList += obj[1][k]
                        else:
                            pass

                logger.debug('(%s) final result: %s' % (PLUGIN_NAME, str(userList)))

            except Exception, e:
                logger.debug(str(e))

        return userList
    except Exception, e:
        logger.debug('(%s) Error: %s' % (PLUGIN_NAME, str(e)))
        return []

def restriction(ldapConn, ldapBaseDn, ldapRecipientDn, ldapRecipientLdif, smtpSessionData, logger, **kargs):
    # Return if recipient is not a mail list object.
    if 'maillist' not in [v.lower() for v in ldapRecipientLdif['objectClass']]:
        return 'DUNNO Not a mail list account.'

    sender = smtpSessionData['sender'].lower()
    sender_domain = sender.split('@')[-1]

    recipient = smtpSessionData['recipient'].lower()
    recipient_domain = recipient.split('@')[-1]

    policy = ldapRecipientLdif.get('accessPolicy', ['public'])[0].lower()

    logger.debug('(%s) Sender: %s' % (PLUGIN_NAME, sender))
    logger.debug('(%s) Recipient: %s' % (PLUGIN_NAME, recipient))
    logger.debug('(%s) Policy: %s' % (PLUGIN_NAME, policy))

    if policy == "public":
        # No restriction.
        return 'DUNNO Access policy: public.'
    elif policy == "domain":
        # Bypass all users under the same domain.
        if sender_domain == recipient_domain:
            return 'DUNNO Access policy: domain'
        else:
            return ACTION_REJECT + ' Access policy: domain.'
    elif policy == "subdomain":
        # Bypass all users under the same domain and sub domains.
        if sender.endswith('.' + recipient_domain):
            return 'DUNNO Access policy: sub domains.'
        else:
            return ACTION_REJECT + ' Access policy: sub domains.'
    else:
        # Handle other access policies: membersOnly, allowedOnly, membersAndModeratorsOnly.
        allowedSenders = __get_allowed_senders(
            ldapConn=ldapConn,
            ldapBaseDn=ldapBaseDn,
            listDn=ldapRecipientDn,
            sender=sender,
            recipient=recipient,
            policy=policy,
            logger=logger,
        )

        if sender.lower() in [v.lower() for v in allowedSenders]:
            return 'DUNNO Allowed sender.'
        else:
            return ACTION_REJECT
