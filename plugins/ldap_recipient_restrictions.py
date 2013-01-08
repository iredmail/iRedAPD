# Author:   Zhang Huangbin <zhb _at_ iredmail.org>
# Updated:  2012-12-30
# Purpose:  Check whether local user (sender) is allowed to mail to recipient

# Value of mailWhitelistRecipient and mailBlacklistRecipient:
#   - Single address:   user@domain.ltd
#   - Whole domain:     @domain.ltd
#   - Whole Domain and its sub-domains: @.domain.ltd
#   - All recipient:       @.

import logging

REQUIRE_LOCAL_SENDER = True
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = ['mailBlacklistedRecipient', 'mailWhitelistRecipient']
RECIPIENT_SEARCH_ATTRLIST = []

def restriction(**kwargs):
    sender_ldif = kwargs['sender_ldif']
    smtp_session_data = kwargs['smtp_session_data']

    # Get recipient address.
    recipient = smtp_session_data.get('recipient').lower()
    splited_recipient_domain = str(recipient.split('@')[-1]).split('.')

    # Get correct domain name and sub-domain name.
    # Sample recipient domain: sub2.sub1.com.cn
    #   -> sub2.sub1.com.cn
    #   -> .sub2.sub1.com.cn
    #   -> .sub1.com.cn
    #   -> .com.cn
    #   -> .cn
    allowed_recipients = ['@.', recipient, '@' + recipient.split('@')[-1],]
    for counter in range(len(splited_recipient_domain)):
        # Append domain and sub-domain.
        allowed_recipients += ['@.' + '.'.join(splited_recipient_domain)]
        splited_recipient_domain.pop(0)

    # Get value of mailBlacklistedRecipient, mailWhitelistRecipient.
    blacklisted_rcpts = [v.lower() for v in sender_ldif.get('mailBlacklistRecipient', [])]
    whitelisted_rcpts = [v.lower() for v in sender_ldif.get('mailWhitelistRecipient', [])]

    # Bypass whitelisted recipients if has intersection set.
    if len(set(allowed_recipients) & set(whitelisted_rcpts)) > 0:
        return 'DUNNO (Whitelisted)'

    # Reject blacklisted recipients if has intersection set.
    if len(set(allowed_recipients) & set(blacklisted_rcpts)) > 0 \
       or '@.' in blacklisted_rcpts:
        return 'REJECT Permission denied'

    # If not matched bl/wl list:
    return 'DUNNO (Not listed in either white/blacklists)'
