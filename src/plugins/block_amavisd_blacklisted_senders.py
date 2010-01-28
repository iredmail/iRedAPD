#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <michaelbibby (at) gmail.com>

import sys

def restriction(smtpSessionData, ldapRecipientLdif, **kargs):
    # Get sender address.
    sender = smtpSessionData.get('sender').lower()

    # Get value of amavisBlacklistedSender.
    blSenders = ldapRecipientLdif.get('amavisBlacklistSender', [])

    if sender in [ v.lower() for v in blSenders ]:
        return 'REJECT Not Authorized'
    else:
        return 'DUNNO'
