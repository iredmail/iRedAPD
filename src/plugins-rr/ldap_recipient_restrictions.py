#!/usr/bin/env python
# encoding: utf-8

# Author:   Zhang Huangbin <zhb (at) iredmail.org>
# Date:     2010-04-20
# Purpose:  Per-user whitelist/blacklist for sender restrictions.
#           Bypass all whitelisted recipients, reject all blacklisted recipients.

# ------------- Addition configure required ------------
# * In postfix main.cf:
#
#   smtpd_sender_restrictions =
#           check_policy_service inet:127.0.0.1:7778,
#           [YOUR OTHER RESTRICTIONS HERE]
#
#   Here, ip address '127.0.0.1' and port number '7778' are set in iRedAPD-RR
#   config file: iredapd-rr.ini.
# ------------------------------------------------------

# Value of mailWhitelistRecipient and mailBlacklistRecipient:
#   - Single address:   user@domain.ltd
#   - Whole domain:     @domain.ltd
#   - Whole Domain and its sub-domains: @.domain.ltd
#   - All sender:       @.

# Debug.
#import logging
#logging.basicConfig(level=logging.DEBUG)

def restriction(smtpSessionData, ldapSenderLdif, **kargs):
    # Get sender address.
    sender = smtpSessionData.get('sender').lower()
    splited_sender_domain = str(sender.split('@')[-1]).split('.')

    # Get correct domain name and sub-domain name.
    # Sample recipient domain: sub2.sub1.com.cn
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

    #logging.debug(str(list_senders))

    # Get value of amavisBlacklistedSender.
    blRecipients = [v.lower()
            for v in ldapSenderLdif.get('mailBlacklistRecipient', [])
            ]
    wlRecipients = [v.lower()
            for v in ldapSenderLdif.get('mailWhitelistRecipient', [])
            ]

    # Bypass whitelisted senders if has intersection set.
    if len(set(list_senders) & set(wlRecipients)) > 0:
        return 'DUNNO'

    # Reject blacklisted senders if has intersection set.
    if len(set(list_senders) & set(blRecipients)) > 0:
        return 'REJECT Not authorized'

    # If not matched bl/wl list:
    return 'DUNNO'
