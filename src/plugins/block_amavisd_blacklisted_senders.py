#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin (zhb@iredmail.org)

import sys

def restriction(smtpSessionData, ldapRecipientLdif, **kargs):
    # Get sender address.
    sender = smtpSessionData.get('sender').lower()
    splited_sender_domain = str(sender.split('@')[-1]).split('.')

    # Get correct domain name and sub-domain name.
    # Sample sender domain: sub2.sub1.com.cn
    #   -> sub2.sub1.com.cn
    #   -> .sub2.sub1.com.cn
    #   -> .sub1.com.cn
    #   -> .com.cn
    #   -> .cn
    list_senders = [sender, '@'+sender.split('@')[-1],]
    for counter in range(len(splited_sender_domain)):
        # Append domain and sub-domain.
        list_senders += ['@.' + '.'.join(splited_sender_domain)]
        splited_sender_domain.pop(0)

    # Get list of amavisBlacklistedSender.
    blSenders = [v.lower() for v in ldapRecipientLdif.get('amavisBlacklistSender', [])]

    # Get list of amavisWhitelistSender.
    wlSenders = [v.lower() for v in ldapRecipientLdif.get('amavisWhitelistSender', [])]

    #
    # Process whitelisted senders first.
    #

    # Bypass whitelisted senders.
    if len(set(list_senders) & set(wlSenders)) > 0:
        return 'DUNNO Whitelisted'

    # Reject blacklisted senders.
    if len(set(list_senders) & set(blSenders)) > 0:
        return 'REJECT Blacklisted'

    # Neither blacklisted nor whitelisted.
    return 'DUNNO No white-/blacklist records found.'
