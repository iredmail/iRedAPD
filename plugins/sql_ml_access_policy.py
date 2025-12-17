# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Apply access policy to sender while recipient is an (mlmmj) mailing
#          list.

# Available access policies:
#   - public:   Unrestricted
#   - domain:   Only users under same domain are allowed.
#   - subdomain:    Only users under same domain and sub domains are allowed.
#   - membersOnly:  Only members are allowed.
#   - moderatorsOnly:   Only moderators are allowed.

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


def restriction(**kwargs):
    conn = kwargs['conn_vmail']
    sender = kwargs['sender_without_ext']
    sender_domain = kwargs['sender_domain']
    # sender_username = sender.split('@', 1)[0]
    recipient = kwargs['recipient_without_ext']
    recipient_domain = kwargs['recipient_domain']

    # used when recipient_domain is an alias domain
    real_recipient_domain = recipient_domain

    policy = get_access_policy(mail=recipient, account_type='maillist', conn=conn)

    # Recipient account doesn't exist.
    if not policy:
        _target_domain = get_alias_target_domain(alias_domain=recipient_domain, conn=conn)
        if not _target_domain:
            logger.debug('Recipient domain is not an alias domain.')
            return SMTP_ACTIONS['default'] + ' Recipient is not a mailing list account.'

        logger.debug('Recipient domain is an alias domain of %s.' % _target_domain)

        # Reset recipient and recipient domain
        real_recipient_domain = _target_domain
        real_recipient = recipient.split('@', 1)[0] + '@' + real_recipient_domain

        policy = get_access_policy(mail=real_recipient, account_type='maillist', conn=conn)
        if not policy:
            return SMTP_ACTIONS['default'] + ' (Recipient is not a mailing list account)'

    logger.debug('Access policy: %s' % policy)

    if policy == MAILLIST_POLICY_PUBLIC:
        return SMTP_ACTIONS['default'] + ' (Access policy is public)'

    # Use 'moderatorsonly' instead of 'allowedonly' (historical value)
    if policy == 'allowedonly':
        policy = MAILLIST_POLICY_MODERATORS

    if policy in (MAILLIST_POLICY_MEMBERSONLY,
                  MAILLIST_POLICY_MEMBERSANDMODERATORSONLY,
                  MAILLIST_POLICY_MODERATORS):
        # Let mlmmj do the ACL
        return SMTP_ACTIONS['default'] + ' (Let mlmmj handle the ACL)'

    # All alias domains of recipient domain
    rcpt_alias_domains = []

    # Check whether sender domain is an alias domain of recipient domain.
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

    # Always bypass moderators.
    addresses = [recipient]
    if rcpt_alias_domains:
        rcpt_username = recipient.split("@")[0]
        addresses.extend([rcpt_username + "@" + d for d in rcpt_alias_domains])

    sql = """SELECT address
               FROM moderators
              WHERE address IN %s
                    AND moderator = %s
              LIMIT 1""" % (sqlquote(addresses), sqlquote(sender))
    logger.debug('[SQL] query moderator: \n%s' % sql)

    _qr = utils.execute_sql(conn, sql)
    _record = _qr.fetchone()
    if _record:
        logger.debug('Sender is a moderator. Bypass.')
        return SMTP_ACTIONS['default']
    else:
        logger.debug('Sender is not a moderator.')

    # Always bypass owners.
    sql = """SELECT address
               FROM maillist_owners
              WHERE address IN %s
                    AND owner = %s
              LIMIT 1""" % (sqlquote(addresses), sqlquote(sender))
    logger.debug('[SQL] query owner: \n%s' % sql)

    _qr = utils.execute_sql(conn, sql)
    _record = _qr.fetchone()
    if _record:
        logger.debug('Sender is an owner. Bypass.')
        return SMTP_ACTIONS['default']
    else:
        logger.debug('Sender is not an owner.')

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

    else:
        # Bypass all if policy is not defined in this plugin.
        return SMTP_ACTIONS['default'] + ' (Unsupported policy: %s. Bypass.)' % policy

    return SMTP_ACTIONS['reject_not_authorized']
