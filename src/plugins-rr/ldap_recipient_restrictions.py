# Author:   Zhang Huangbin <zhb _at_ iredmail.org>
# Date:     2010-04-20
# Purpose:  Per-user whitelist/blacklist for recipient restrictions.
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
#   - All recipient:       @.

def restriction(smtpSessionData, ldapSenderLdif, **kargs):
    # Get recipient address.
    smtpRecipient = smtpSessionData.get('recipient').lower()
    splited_recipient_domain = str(smtpRecipient.split('@')[-1]).split('.')

    # Get correct domain name and sub-domain name.
    # Sample recipient domain: sub2.sub1.com.cn
    #   -> sub2.sub1.com.cn
    #   -> .sub2.sub1.com.cn
    #   -> .sub1.com.cn
    #   -> .com.cn
    #   -> .cn
    recipients = ['@.', smtpRecipient, '@' + smtpRecipient.split('@')[-1],]
    for counter in range(len(splited_recipient_domain)):
        # Append domain and sub-domain.
        recipients += ['@.' + '.'.join(splited_recipient_domain)]
        splited_recipient_domain.pop(0)

    # Get value of mailBlacklistedRecipient, mailWhitelistRecipient.
    blRecipients = [v.lower()
            for v in ldapSenderLdif.get('mailBlacklistRecipient', [])
            ]

    wlRecipients = [v.lower()
            for v in ldapSenderLdif.get('mailWhitelistRecipient', [])
            ]

    # Bypass whitelisted recipients if has intersection set.
    if len(set(recipients) & set(wlRecipients)) > 0:
        return 'DUNNO'

    # Reject blacklisted recipients if has intersection set.
    if len(set(recipients) & set(blRecipients)) > 0 or '@.' in blRecipients:
        return 'REJECT Permission denied'

    # If not matched bl/wl list:
    return 'DUNNO'
