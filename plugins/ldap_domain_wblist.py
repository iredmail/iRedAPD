# Author: Zhang Huangbin <zhb _at_ iredmail.org>

# ----------------------------------------------------------------------------
# This plugin is used for per-domain white-/blacklist.
# ----------------------------------------------------------------------------

import logging

REQUIRE_LOCAL_SENDER = False
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = []
RECIPIENT_SEARCH_ATTRLIST = []


def restriction(**kwargs):
    conn = kwargs['conn']
    base_dn = kwargs['base_dn']
    smtp_session_data = kwargs['smtp_session_data']

    sender = smtp_session_data['sender'].lower()
    splitedSenderDomain = str(sender.split('@')[-1]).split('.')

    filterOfSenders = ''
    listOfRestrictedSenders = [sender, '@'+sender.split('@')[-1],]
    for counter in range(len(splitedSenderDomain)):
        # Append domain and sub-domain.
        listOfRestrictedSenders += ['@.' + '.'.join(splitedSenderDomain)]
        splitedSenderDomain.pop(0)

    for i in listOfRestrictedSenders:
        filterOfSenders += '(domainWhitelistSender=%s)(domainBlacklistSender=%s)' % (i, i,)

    recipient = smtp_session_data['recipient'].lower()
    recipientDomain = recipient.split('@')[-1]

    logging.debug('Sender: %s' % sender)
    logging.debug('Recipient: %s' % recipient)

    # Query ldap to get domain dn, with domain alias support.
    try:
        resultDnOfDomain = conn.search_s(
            base_dn,
            1,                  # 1 = ldap.SCOPE_ONELEVEL
            '(|(domainName=%s)(domainAliasName=%s))' % (recipientDomain, recipientDomain),
            ['dn'],
        )
        dnOfRecipientDomain = resultDnOfDomain[0][0]
        logging.debug('DN of recipient domain: %s' % dnOfRecipientDomain)
    except Exception, e:
        return 'DUNNO (Error while fetching domain dn: %s)' % (str(e))

    # Get list of restricted ip addresses.
    senderIP = smtp_session_data['client_address']
    (ipf1, ipf2, ipf3, ipf4) = senderIP.split('.')
    listOfRestrictedIPAddresses = [
        senderIP,                           # xx.xx.xx.xx
        '.'.join([ipf1, '%.%', ipf4]),      # xx.%.%.xx
        '.'.join([ipf1, '%', ipf3, ipf4]),  # xx.%.xx.xx
        '.'.join([ipf1, '%', ipf3, '%']),   # xx.%.xx.%
        '.'.join([ipf1, '%.%.%']),          # xx.%.%.%
        '.'.join([ipf1, ipf2, '%', ipf4]),  # xx.xx.%.xx
        '.'.join([ipf1, ipf2, '%.%']),      # xx.xx.%.%
        '.'.join([ipf1, ipf2, ipf3, '%']),  # xx.xx.xx.%
        '%.%.%.%',                          # %.%.%.% Matches all IP addresses.
    ]

    filterOfIPAddr = ''
    for i in listOfRestrictedIPAddresses:
        filterOfIPAddr += '(domainWhitelistIP=%s)(domainBlacklistIP=%s)' % (i, i,)

    # Generate final search filter.
    filter = '(&(objectClass=mailDomain)(|(domainName=%s)(domainAliasName=%s))(|%s))' % (
        recipientDomain,
        recipientDomain,
        filterOfSenders + filterOfIPAddr,
    )

    try:
        resultWblists = conn.search_s(
            dnOfRecipientDomain,    # Base dn.
            0,                      # Search scope. 0 = ldap.SCOPE_BASE
            filter,                 # Search filter.
            ['domainWhitelistIP', 'domainWhitelistSender', 'domainBlacklistIP', 'domainBlacklistSender', ],
        )

        if len(resultWblists) == 0:
            # No white/blacklist available.
            return 'DUNNO (No white/blacklist found)'

        ###################
        # Whitelist first.
        #
        whitelistedSenders = resultWblists[0][1].get('domainWhitelistSender', [])
        whitelistedIPAddresses = resultWblists[0][1].get('domainWhitelistIP', [])

        logging.debug('Whitelisted senders: %s' % ', '.join(whitelistedSenders))
        logging.debug('Whitelisted IP addresses: %s' % ', '.join(whitelistedIPAddresses))

        if len(set(listOfRestrictedSenders) & set(whitelistedSenders)) > 0 or \
           len(set(listOfRestrictedIPAddresses) & set(whitelistedIPAddresses)) > 0:
            return 'DUNNO (Whitelisted)'

        ###################
        # Blacklist.
        #
        blacklistedSenders = resultWblists[0][1].get('domainBlacklistSender', [])
        blacklistedIPAddresses = resultWblists[0][1].get('domainBlacklistIP', [])

        logging.debug('Blacklisted senders: %s' % ', '.join(blacklistedSenders))
        logging.debug('Blacklisted IP addresses: %s' % ', '.join(blacklistedIPAddresses))

        if len(set(listOfRestrictedSenders) & set(blacklistedSenders)) > 0 or \
           len(set(listOfRestrictedIPAddresses) & set(blacklistedIPAddresses)) > 0:
            return 'REJECT Blacklisted'

        return 'DUNNO (Not listed in white/blacklist records)'
    except Exception, e:
        # Error while quering LDAP server, return 'DUNNO' instead of rejecting emails.
        return 'DUNNO (Error while fetching white/blacklist records: %s)' % (str(e))
