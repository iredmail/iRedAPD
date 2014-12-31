# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Apply access policy on sender while recipient is an mail alias.

# Available access policies:
#   - public:   Unrestricted
#   - domain:   Only users under same domain are allowed.
#   - subdomain:    Only users under same domain and sub domains are allowed.
#   - membersOnly:  Only members are allowed.
#   - moderatorsOnly:   Only moderators are allowed.
#   - membersAndModeratorsOnly: Only members and moderators are allowed.

import logging
from libs import SMTP_ACTIONS
from libs import MAILLIST_POLICY_PUBLIC
from libs import MAILLIST_POLICY_DOMAIN
from libs import MAILLIST_POLICY_SUBDOMAIN
from libs import MAILLIST_POLICY_MEMBERSONLY
from libs import MAILLIST_POLICY_ALLOWEDONLY
from libs import MAILLIST_POLICY_MEMBERSANDMODERATORSONLY


def is_allowed_alias_domain_user(sender,
                                 sender_username,
                                 sender_domain,
                                 recipient_domain,
                                 rcpt_alias_domains,
                                 restricted_members):
    if sender_domain in rcpt_alias_domains:
        policy_senders = [sender, sender_username + '@' + recipient_domain]
        policy_senders += [sender_username + '@' + d for d in rcpt_alias_domains]

        matched_senders = set(policy_senders) & set(restricted_members)
        if matched_senders:
            logging.debug('Matched alias domain user: %s' % str(matched_senders))
            return True

    return False


def restriction(**kwargs):
    conn = kwargs['conn']
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    sender_username = sender.split('@', 1)[0]
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    sql = '''SELECT accesspolicy, goto, moderators
            FROM alias
            WHERE
                address='%s'
                AND address <> goto
                AND active=1
            LIMIT 1
    ''' % (recipient)
    logging.debug('SQL: query access policy: %s' % sql)

    conn.execute(sql)
    sql_record = conn.fetchone()
    logging.debug('SQL: record: %s' % str(sql_record))

    # Recipient account doesn't exist.
    if not sql_record:
        return 'DUNNO (Not mail alias)'

    policy = str(sql_record[0]).lower()
    if not policy:
        policy = 'public'

    # Log access policy and description
    logging.debug('Access policy: %s' % policy)

    members = [str(v.lower()) for v in str(sql_record[1]).split(',')]
    moderators = [str(v.lower()) for v in str(sql_record[2]).split(',')]

    logging.debug('members: %s' % ', '.join(members))
    logging.debug('moderators: %s' % ', '.join(moderators))

    rcpt_alias_domains = []
    if policy != MAILLIST_POLICY_PUBLIC:
        # Get alias domains.
        sql = """SELECT alias_domain
                 FROM alias_domain
                 WHERE alias_domain='%s' AND target_domain='%s'
                 LIMIT 1""" % (sender_domain, recipient_domain)
        logging.debug('SQL: query alias domains: %s' % sql)

        conn.execute(sql)
        qr = conn.fetchone()
        logging.debug('SQL: record: %s' % str(qr))

        if qr:
            rcpt_alias_domains.append(str(qr[0]))

    if policy == MAILLIST_POLICY_PUBLIC:
        # Return if no access policy available or policy is @POLICY_PUBLIC.
        return 'DUNNO'
    elif policy == MAILLIST_POLICY_DOMAIN:
        # Bypass all users under the same domain.
        if sender_domain == recipient_domain or sender_domain in rcpt_alias_domains:
            return 'DUNNO'
        else:
            return SMTP_ACTIONS['reject_not_authorized']
    elif policy == MAILLIST_POLICY_SUBDOMAIN:
        # Bypass all users under the same domain or sub domains.
        if sender_domain == recipient_domain or sender.endswith('.' + recipient_domain):
            return 'DUNNO'

        if rcpt_alias_domains:
            for d in rcpt_alias_domains:
                if sender_domain == d or sender.endswith('.' + d):
                    logging.debug('Matched: %s or .%s' % (d, d))
                    return 'DUNNO'

        return SMTP_ACTIONS['reject_not_authorized']

    elif policy == MAILLIST_POLICY_MEMBERSONLY:
        # Bypass all members.
        if sender in members \
           or is_allowed_alias_domain_user(sender,
                                           sender_username,
                                           sender_domain,
                                           recipient_domain,
                                           rcpt_alias_domains,
                                           members):
            return 'DUNNO'

        return SMTP_ACTIONS['reject_not_authorized']

    elif policy == MAILLIST_POLICY_ALLOWEDONLY:
        # Bypass all moderators.
        if sender in moderators \
           or is_allowed_alias_domain_user(sender,
                                           sender_username,
                                           sender_domain,
                                           recipient_domain,
                                           rcpt_alias_domains,
                                           moderators):
            return 'DUNNO'

        return SMTP_ACTIONS['reject_not_authorized']

    elif policy == MAILLIST_POLICY_MEMBERSANDMODERATORSONLY:
        # Bypass both members and moderators.
        if sender in members or sender in moderators\
           or is_allowed_alias_domain_user(sender,
                                           sender_username,
                                           sender_domain,
                                           recipient_domain,
                                           rcpt_alias_domains,
                                           members + moderators):
            return 'DUNNO'

        return SMTP_ACTIONS['reject_not_authorized']
    else:
        # Bypass all if policy is not defined in this plugin.
        return 'DUNNO (Policy is not defined: %s)' % policy
