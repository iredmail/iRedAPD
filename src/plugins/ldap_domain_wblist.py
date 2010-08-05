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
from ldap.filter import escape_filter_chars

ACTION_REJECT = 'REJECT Not Authorized'

# smtp session data
#   * sasl username
#   * recipient address
# LDIF of domain

def restriction(ldapConn, ldapBaseDn, smtpSessionData, **kargs):
    sender = smtpSessionData['sender'].lower()
    senderDomain = sender.split('@')[-1]
    splitedSenderDomain = str(sender.split('@')[-1]).split('.')

    #filterOfSender = '(domainWhitelistSender=%s)' % (sender,)
    filterOfSenders = ''
    listOfRestrictedSenders = [sender, '@'+sender.split('@')[-1],]
    for counter in range(len(splitedSenderDomain)):
        # Append domain and sub-domain.
        listOfRestrictedSenders += ['@.' + '.'.join(splitedSenderDomain)]
        splitedSenderDomain.pop(0)

    for i in listOfRestrictedSenders:
        filterOfSenders += '(domainWhitelistSender=%s)(domainBlacklistSender=%s)' % (i, i,)

    recipient = smtpSessionData['recipient'].lower()
    recipientDomain = recipient.split('@')[-1]
    dnOfRecipientDomain = escape_filter_chars('domainName=' + recipientDomain + ',' + ldapBaseDn)

    # Get list of restricted ip addresses.
    senderIP = smtpSessionData['client_address']
    (ipf1, ipf2, ipf3, ipf4) = senderIP.split('.')
    listOfRestrictedIPAddresses = [senderIP,
                '.'.join([ipf1, '%', ipf3, ipf4]),
                '.'.join([ipf1, ipf2, '%', ipf4]),
                '.'.join([ipf1, ipf2, ipf3, '%']),
               ]

    filterOfIPAddr = ''
    for i in listOfRestrictedIPAddresses:
        filterOfIPAddr += '(domainWhitelistIP=%s)(domainBlacklistIP=%s)' % (i, i,)

    # Generate final search filter.
    filter = '(&(objectClass=mailDomain)(domainName=%s)(|%s))' % (
        recipientDomain,
        filterOfSenders + filterOfIPAddr,
    )

    try:
        resultWblists = ldapConn.search_s(
            dnOfRecipientDomain,    # Base dn.
            0,                      # Search scope. 0 = ldap.SCOPE_BASE
            filter,                 # Search filter.
            ['domainWhitelistIP', 'domainWhitelistSender', 'domainBlacklistIP', 'domainBlacklistSender', ],
        )

        if len(resultWblists) == 0:
            # No white/blacklist available.
            return 'DUNNO'

        # Whitelist first.
        whitelistedSenders = resultWblists[0][1].get('domainWhitelistSender', [])
        whitelistedIPAddresses = resultWblists[0][1].get('domainWhitelistIP', [])

        if len(set(listOfRestrictedSenders) & set(whitelistedSenders)) > 0 or \
           len(set(listOfRestrictedIPAddresses) & set(whitelistedIPAddresses)) > 0:
            return 'DUNNO Whitelisted'

        # Blacklist.
        blacklistedSenders = resultWblists[0][1].get('domainBlacklistSender', [])
        blacklistedIPAddresses = resultWblists[0][1].get('domainBlacklistIP', [])

        if len(set(listOfRestrictedSenders) & set(blacklistedSenders)) > 0 or \
           len(set(listOfRestrictedIPAddresses) & set(blacklistedIPAddresses)) > 0:
            return 'REJECT Blacklisted'

        return 'DUNNO'
    except Exception, e:
        # Error while quering LDAP server, return 'DUNNO' instead of rejecting emails.
        return 'DUNNO'
