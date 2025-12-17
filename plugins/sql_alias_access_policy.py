# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Apply access policy on sender while recipient is an mail alias.

# Available access policies:
#   - public:   Unrestricted
#   - domain:   Only users under same domain are allowed.
#   - subdomain:    Only users under same domain and sub domains are allowed.
#   - membersOnly:  Only members are allowed.
#   - moderatorsOnly:   Only moderators are allowed.
#   - membersAndModeratorsOnly: Only members and moderators are allowed.

from web import sqlquote
from libs.logger import logger
from libs import utils
from libs import SMTP_ACTIONS
from libs import MAILLIST_POLICY_PUBLIC
from libs import MAILLIST_POLICY_DOMAIN
from libs import MAILLIST_POLICY_SUBDOMAIN
from libs import MAILLIST_POLICY_MEMBERSONLY
from libs import MAILLIST_POLICY_MODERATORS
from libs import MAILLIST_POLICY_MEMBERSANDMODERATORSONLY

from libs.sql import get_access_policy, get_alias_target_domain


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
            logger.debug('Matched alias domain user: %s' % str(matched_senders))
            return True

    return False


def get_members(conn, mail):
    """Return a list of members of mail alias account."""
    _members = []

    # Get access policy directly.
    sql = """SELECT forwarding
               FROM forwardings
              WHERE address=%s AND is_list=1""" % sqlquote(mail)

    logger.debug('[SQL] query alias members: \n%s' % sql)

    qr = utils.execute_sql(conn, sql)
    records = qr.fetchall()
    logger.debug('SQL query result: %s' % str(records))

    if records:
        for i in records:
            _members.append(str(i[0]).lower())

    return _members


def get_moderators(conn, mail):
    """Return a list of moderators of mail alias account."""
    _moderators = []

    # Get access policy directly.
    sql = """SELECT moderator
               FROM moderators
              WHERE address=%s""" % sqlquote(mail)

    logger.debug('[SQL] query moderators: \n%s' % sql)

    qr = utils.execute_sql(conn, sql)
    records = qr.fetchall()
    logger.debug('SQL query result: %s' % str(records))

    if records:
        for i in records:
            _moderators.append(str(i[0]).lower())

    return _moderators


def restriction(**kwargs):
    conn = kwargs['conn_vmail']
    sender = kwargs['sender_without_ext']
    sender_domain = kwargs['sender_domain']
    sender_username = sender.split('@', 1)[0]
    recipient = kwargs['recipient_without_ext']
    recipient_domain = kwargs['recipient_domain']
    real_recipient = recipient

    # used when recipient_domain is an alias domain
    real_recipient_domain = recipient_domain

    policy = get_access_policy(mail=recipient, account_type='alias', conn=conn)

    # Recipient account doesn't exist.
    if not policy:
        _target_domain = get_alias_target_domain(alias_domain=recipient_domain, conn=conn)
        if not _target_domain:
            logger.debug('Recipient domain is not an alias domain.')
            return SMTP_ACTIONS['default'] + ' Recipient is not a mail alias account or no access policy'

        # Reset recipient and recipient domain
        real_recipient_domain = _target_domain
        real_recipient = recipient.split('@', 1)[0] + '@' + real_recipient_domain

        policy = get_access_policy(mail=real_recipient, account_type='alias', conn=conn)
        if not policy:
            return SMTP_ACTIONS['default'] + ' (Recipient domain is an alias domain, but recipient is not a mail alias account)'

    if not policy:
        return SMTP_ACTIONS['default'] + ' (Recipient is not a mail alias account)'

    logger.debug('Access policy: %s' % policy)

    if policy == MAILLIST_POLICY_PUBLIC:
        return SMTP_ACTIONS['default'] + ' (Access policy is public)'

    # Use 'moderatorsonly' instead of 'allowedonly' (historical value)
    if policy == 'allowedonly':
        policy = MAILLIST_POLICY_MODERATORS

    # All alias domains of recipient domain
    rcpt_alias_domains = []

    # Get alias domains.
    sql = """SELECT alias_domain
               FROM alias_domain
              WHERE alias_domain=%s AND target_domain=%s
              LIMIT 1
              """ % (sqlquote(sender_domain), sqlquote(real_recipient_domain))
    logger.debug('[SQL] query alias domain: \n%s' % sql)

    _qr = utils.execute_sql(conn, sql)
    _record = _qr.fetchone()

    if _record:
        logger.debug('SQL query result: %s' % str(_record))
        rcpt_alias_domains.append(str(_record[0]))
    else:
        logger.debug('No alias domain.')

    members = []
    moderators = []
    if policy in (MAILLIST_POLICY_MEMBERSONLY, MAILLIST_POLICY_MEMBERSANDMODERATORSONLY):
        members = get_members(conn=conn, mail=real_recipient)
        logger.debug('Members: %s' % ', '.join(members))

    if policy in (MAILLIST_POLICY_MODERATORS, MAILLIST_POLICY_MEMBERSANDMODERATORSONLY):
        moderators = get_moderators(conn=conn, mail=real_recipient)
        logger.debug('Moderators: %s' % ', '.join(moderators))

    if policy == MAILLIST_POLICY_DOMAIN:
        # Bypass all users under the same domain.
        if sender_domain == recipient_domain \
           or sender_domain == real_recipient_domain \
           or sender_domain in rcpt_alias_domains:
            return SMTP_ACTIONS['default']

    elif policy == MAILLIST_POLICY_SUBDOMAIN:
        # Bypass all users under the same domain or sub domains.
        if sender_domain == recipient_domain \
           or sender_domain == real_recipient_domain \
           or sender.endswith('.' + recipient_domain) \
           or sender.endswith('.' + real_recipient_domain):
            logger.debug('Sender domain is same as recipient domain or is sub-domain.')
            return SMTP_ACTIONS['default']
        elif sender_domain in rcpt_alias_domains:
            logger.debug('Sender domain is one of recipient alias domains.')
            return SMTP_ACTIONS['default']
        else:
            # Check whether sender domain is subdomain of primary/alias recipient domains
            for d in rcpt_alias_domains:
                if sender.endswith('.' + d):
                    logger.debug('Sender domain is sub-domain of recipient alias domains: %s' % d)
                    return SMTP_ACTIONS['default']

    elif policy == MAILLIST_POLICY_MODERATORS:
        # Bypass all moderators.
        if sender in moderators \
           or '*@' + sender_domain in moderators \
           or is_allowed_alias_domain_user(sender,
                                           sender_username,
                                           sender_domain,
                                           recipient_domain,
                                           rcpt_alias_domains,
                                           moderators):
            return SMTP_ACTIONS['default']

    elif policy == MAILLIST_POLICY_MEMBERSONLY:
        # Bypass all members.
        if sender in members \
           or is_allowed_alias_domain_user(sender,
                                           sender_username,
                                           sender_domain,
                                           recipient_domain,
                                           rcpt_alias_domains,
                                           members):
            return SMTP_ACTIONS['default']

    elif policy == MAILLIST_POLICY_MEMBERSANDMODERATORSONLY:
        # Bypass both members and moderators.
        if sender in members \
           or sender in moderators \
           or '*@' + sender_domain in moderators \
           or is_allowed_alias_domain_user(sender,
                                           sender_username,
                                           sender_domain,
                                           recipient_domain,
                                           rcpt_alias_domains,
                                           members + moderators):
            return SMTP_ACTIONS['default']
    else:
        # Bypass all if policy is not defined in this plugin.
        return SMTP_ACTIONS['default'] + ' (Unsupported policy: %s. Bypass.)' % policy

    return SMTP_ACTIONS['reject_not_authorized']
