# Author: Zhang Huangbin <zhb _at_ iredmail.org>

#----------
# WARNING: This plugin is deprecated, please use `amavisd_wblist` instead.
#----------

# Priority: whitelist first, then blacklist.

import logging
from libs import SMTP_ACTIONS
from libs.amavisd import core as amavisd_lib

RECIPIENT_SEARCH_ATTRLIST = ['amavisBlacklistSender', 'amavisWhitelistSender']

def restriction(**kwargs):
    recipient_ldif = kwargs['recipient_ldif']

    # Return if recipient doesn't have objectClass=amavisdAccount.
    if not recipient_ldif:
        return 'DUNNO (No recipient LDIF data)'

    if not 'amavisAccount' in recipient_ldif.get('objectClass', []):
        return 'DUNNO (Not a amavisdAccount object)'

    sender = kwargs['sender']

    # Get valid Amavisd senders
    valid_senders = amavisd_lib.get_valid_addresses_from_email(sender)

    # Get list of amavisBlacklistedSender.
    blSenders = set([v.lower() for v in recipient_ldif.get('amavisBlacklistSender', [])])

    # Get list of amavisWhitelistSender.
    wlSenders = set([v.lower() for v in recipient_ldif.get('amavisWhitelistSender', [])])

    logging.debug('Sender: %s' % sender)
    logging.debug('Whitelisted senders: %s' % str(wlSenders))
    logging.debug('Blacklisted senders: %s' % str(blSenders))

    # Bypass whitelisted senders.
    if set(valid_senders) & wlSenders:
        return SMTP_ACTIONS['accept']

    # Reject blacklisted senders.
    if set(valid_senders) & blSenders:
        return 'REJECT Blacklisted'

    # Neither blacklisted nor whitelisted.
    return 'DUNNO (No white/blacklist records found)'
