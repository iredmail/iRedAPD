#!/usr/bin/env python
# encoding: utf-8

# Author: Zhang Huangbin <michaelbibby (at) gmail.com>
# Date: 2010-03-12
# Purpose: Apply access policy on sender while recipient is an alias.

# -------- ALTER MYSQL TABLE BEFORE ENABLE THIS PLUGIN -----------
#   mysql> USE vmail;
#   mysql> ALTER TABLE alias ADD COLUMN accesspolicy VARCHAR(30) NOT NULL DEFAULT '';
#   mysql> ALTER TABLE alias ADD COLUMN moderators TEXT NOT NULL DEFAULT '';
# --------

# Handled policies:
#   - public:   Unrestricted
#   - domain:   Only users under same domain are allowed.
#   - subdomain:    Only users under same domain and sub domains are allowed.
#   - membersOnly:  Only members are allowed.
#   - moderatorsOnly:   Only moderators are allowed.
#   - membersAndModeratorsOnly: Only members and moderators are allowed.

import sys

ACTION_REJECT = 'REJECT Not Authorized'

# Policies. MUST be defined in lower case.
POLICY_PUBLIC = 'public'
POLICY_DOMAIN = 'domain'
POLICY_SUBDOMAIN = 'subdomain'
POLICY_MEMBERSONLY = 'membersonly'
POLICY_MODERATORSONLY = 'moderatorsonly'
POLICY_ALLOWEDONLY = 'allowedOnly'      # Same as @POLICY_MODERATORSONLY
POLICY_MEMBERSANDMODERATORSONLY = 'membersandmoderatorsonly'

def restriction(dbConn, senderReceiver, smtpSessionData, **kargs):
    # Get alias account from alias table.
    # If you need to run RAW SQL command, use dbConn.query() instead.
    # Reference: http://webpy.org/cookbook/query
    # Sample:
    #   result = dbConn.query('''SELECT * FROM alias WHERE address=$recipient''', vars=senderReceiver,)

    result = dbConn.select('alias',
                           senderReceiver,
                           where='address = $recipient AND domain = $recipient_domain',
                           limit=1,
                          )

    # Return if recipient account doesn't exist.
    if len(result) != 1:
        return 'DUNNO'

    # Use the first SQL record.
    sqlRecord = result[0]

    policy = sqlRecord.get('accesspolicy', 'public').lower()

    members = [str(v.lower()) for v in sqlRecord.get('goto', '').split(',')]
    moderators = [str(v.lower()) for v in sqlRecord.get('moderators', '').split(',')]

    if policy == POLICY_PUBLIC:
        # Return if no access policy available or policy is @POLICY_PUBLIC.
        return 'DUNNO'
    elif policy == POLICY_DOMAIN:
        # Bypass all users under the same domain.
        if senderReceiver['sender_domain'] == senderReceiver['recipient_domain']:
            return 'DUNNO'
        else:
            return ACTION_REJECT
    elif policy == POLICY_SUBDOMAIN:
        # Bypass all users under the same domain or sub domains.
        if senderReceiver['sender'].endswith('.' + senderReceiver['recipient_domain']):
            return 'DUNNO'
        else:
            return ACTION_REJECT
    elif policy == POLICY_MEMBERSONLY:
        # Bypass all members.
        if senderReceiver['sender'] in members:
            return 'DUNNO'
        else:
            return ACTION_REJECT
    elif policy == POLICY_MODERATORSONLY or policy == POLICY_ALLOWEDONLY:
        # Bypass all moderators.
        if senderReceiver['sender'] in moderators:
            return 'DUNNO'
        else:
            return ACTION_REJECT
    elif policy == POLICY_MEMBERSANDMODERATORSONLY:
        # Bypass both members and moderators.
        if senderReceiver['sender'] in members or senderReceiver['sender'] in moderators:
            return 'DUNNO'
        else:
            return ACTION_REJECT
    else:
        # Bypass all if policy is not defined in this plugin.
        return 'DUNNO'
