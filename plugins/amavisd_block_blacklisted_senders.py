# Author: Zhang Huangbin <zhb _at_ iredmail.org>

# Priority: whitelist first, then blacklist.

import logging
from libs import SMTP_ACTIONS

REQUIRE_LOCAL_SENDER = False
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = []
RECIPIENT_SEARCH_ATTRLIST = ['amavisBlacklistSender', 'amavisWhitelistSender']


def restriction(**kwargs):
    smtpSessionData = kwargs['smtpSessionData']
    ldapRecipientLdif = kwargs['recipientLdif']
    # Get sender address.
    sender = smtpSessionData.get('sender').lower()

    # Get valid Amavisd sender, sender domain and sub-domain(s).
    # - Sample user: user@sub2.sub1.com.cn
    # - Valid Amavisd senders:
    #   -> user@sub2.sub1.com.cn
    #   -> @sub2.sub1.com.cn
    #   -> @.sub2.sub1.com.cn
    #   -> @.sub1.com.cn
    #   -> @.com.cn
    #   -> @.cn
    splited_sender_domain = str(sender.split('@', 1)[-1]).split('.')

    # Default senders (user@domain.ltd):
    # ['@.', 'user@domain.ltd', @domain.ltd']
    valid_amavisd_senders = set(['@.', sender, '@' + sender.split('@', 1)[-1], ])
    for counter in range(len(splited_sender_domain)):
        # Append domain and sub-domain.
        valid_amavisd_senders.update(['@.' + '.'.join(splited_sender_domain)])
        splited_sender_domain.pop(0)

    # Get list of amavisBlacklistedSender.
    blSenders = set([v.lower() for v in ldapRecipientLdif.get('amavisBlacklistSender', [])])

    # Get list of amavisWhitelistSender.
    wlSenders = set([v.lower() for v in ldapRecipientLdif.get('amavisWhitelistSender', [])])

    logging.debug('Sender: %s' % sender)
    logging.debug('Whitelisted senders: %s' % str(wlSenders))
    logging.debug('Blacklisted senders: %s' % str(blSenders))

    # Bypass whitelisted senders.
    if len(valid_amavisd_senders & wlSenders) > 0:
        return SMTP_ACTIONS['accept']

    # Reject blacklisted senders.
    if len(valid_amavisd_senders & blSenders) > 0:
        return 'REJECT Blacklisted'

    # Neither blacklisted nor whitelisted.
    return 'DUNNO (No white/blacklist records found)'
