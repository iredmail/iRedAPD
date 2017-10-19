# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Restrict who can send email to mail list.
# Note: Available access policy names are defined in file `libs/__init__.py`.

from libs.logger import logger
from libs import utils
from libs import SMTP_ACTIONS
from libs import MAILLIST_POLICY_PUBLIC
from libs import MAILLIST_POLICY_DOMAIN
from libs import MAILLIST_POLICY_SUBDOMAIN
from libs import MAILLIST_POLICY_MEMBERSONLY
from libs import MAILLIST_POLICY_MODERATORS
from libs import MAILLIST_POLICY_MEMBERSANDMODERATORSONLY

from libs.ldaplib import conn_utils
import settings

REQUIRE_LOCAL_RECIPIENT = True
RECIPIENT_SEARCH_ATTRLIST = ['listAllowedUser', 'accessPolicy']


def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']
    recipient = kwargs['recipient_without_ext']
    recipient_ldif = kwargs['recipient_ldif']

    if sasl_username == recipient:
        return SMTP_ACTIONS['default'] + ' (sasl_username == recipient, not a mail list account)'

    # Pass if recipient doesn't exist (no LDIF data)
    if not recipient_ldif:
        return SMTP_ACTIONS['default'] + ' (Recipient is not a local account - no LDIF data)'

    # Pass if recipient is not a mailing list account
    if 'mailList' not in recipient_ldif['objectClass']:
        return SMTP_ACTIONS['default'] + ' (Recipient is not a mailing list account)'

    # Get access policy
    policy = recipient_ldif.get('accessPolicy', [MAILLIST_POLICY_PUBLIC])[0].lower()

    # Log access policy
    logger.debug('Access policy of mailing list (%s): %s' % (recipient, policy))
    if policy == MAILLIST_POLICY_PUBLIC:
        return SMTP_ACTIONS['default'] + ' (Access policy: %s, no restriction)' % MAILLIST_POLICY_PUBLIC

    conn = kwargs['conn_vmail']
    sender = kwargs['sender_without_ext']
    sender_domain = kwargs['sender_domain']
    recipient_domain = kwargs['recipient_domain']

    # Get primary recipient domain and all its alias domains
    valid_rcpt_domains = conn_utils.get_primary_and_alias_domains(conn=conn,
                                                                  domain=recipient_domain)
    logger.debug('Primary and all alias domain names of recipient domain (%s): %s' % (recipient_domain, ', '.join(valid_rcpt_domains)))

    #
    # No matter what access policy it has, bypass explictly allowed senders
    #
    explicitly_allowed_senders = recipient_ldif.get('listAllowedUser', [])

    # Check sender and sender domains
    if sender in explicitly_allowed_senders:
        return SMTP_ACTIONS['default'] + '  (Sender is allowed explicitly: %s)' % sender
    elif sender_domain in explicitly_allowed_senders or '*@' + sender_domain in explicitly_allowed_senders:
        return SMTP_ACTIONS['default'] + '  (Sender domain is allowed explicitly: %s)' % sender_domain

    # Check all possible sender domains (without checking sender alias domains)
    _possible_sender_domains = [sender_domain]
    _domain_parts = sender_domain.split('.')
    for i in _domain_parts:
        _possible_sender_domains += ['.' + '.'.join(_domain_parts)]
        _domain_parts.pop(0)

    logger.debug('Sender domain and sub-domains: %s' % ', '.join(_possible_sender_domains))
    if set(_possible_sender_domains) & set(explicitly_allowed_senders):
        return SMTP_ACTIONS['default'] + ' (Sender domain or its sub-domain is explicitly allowed)'

    logger.debug('Sender is not explicitly allowed, perform extra LDAP query to check access.')

    # Get domain dn.
    dn_rcpt_domain = 'domainName=' + recipient_domain + ',' + settings.ldap_basedn

    # Verify access policies
    if policy in [MAILLIST_POLICY_DOMAIN, MAILLIST_POLICY_SUBDOMAIN]:
        if policy == MAILLIST_POLICY_DOMAIN:
            # Bypass all users under the same domain.
            if sender_domain in valid_rcpt_domains:
                return SMTP_ACTIONS['default'] + ' (Sender bypasses access policy: %s (%s))' % (MAILLIST_POLICY_DOMAIN, sender_domain)

        elif policy == MAILLIST_POLICY_SUBDOMAIN:
            # Bypass all users under the same domain and all sub domains.
            for d in valid_rcpt_domains:
                if sender_domain == d or sender_domain.endswith('.' + d):
                    return SMTP_ACTIONS['default'] + ' (Sender bypasses access policy: %s (%s))' % (MAILLIST_POLICY_SUBDOMAIN, d)

        return SMTP_ACTIONS['reject_not_authorized']

    elif policy == MAILLIST_POLICY_MEMBERSONLY:
        # Get all members of mailing list.
        _f = '(&' + \
             '(accountStatus=active)(memberOfGroup=%s)' % (recipient) + \
             '(|(objectclass=mailUser)(objectClass=mailExternalUser))' + \
             ')'

        # Get both mail and shadowAddress.
        search_attrs = ['mail', 'shadowAddress']

        logger.debug('search base dn: %s' % dn_rcpt_domain)
        logger.debug('search scope: SUBTREE')
        logger.debug('search filter: %s' % _f)
        logger.debug('search attributes: %s' % ', '.join(search_attrs))

        qr = conn.search_s(dn_rcpt_domain, 2, _f, search_attrs)

        allowed_senders = []
        for (_dn, _ldif) in qr:
            for k in search_attrs:
                allowed_senders += _ldif.get(k, [])

        if sender in allowed_senders:
            return SMTP_ACTIONS['default'] + ' (Sender bypasses access policy: %s (%s))' % (MAILLIST_POLICY_MEMBERSONLY, sender)

        return SMTP_ACTIONS['reject_not_authorized']

    elif policy in ['allowedonly', MAILLIST_POLICY_MEMBERSANDMODERATORSONLY]:
        # 'allowedonly' is policy name used by old iRedAPD.
        # Get both members and moderators.
        _f = '(|' + \
             '(&(memberOfGroup=%s)(|(objectClass=mailUser)(objectClass=mailExternalUser)))' % recipient + \
             '(&(objectclass=mailList)(mail=%s))' % recipient + \
             ')'
        search_attrs = ['mail', 'shadowAddress', 'listAllowedUser']

        logger.debug('search base dn: %s' % dn_rcpt_domain)
        logger.debug('search scope: SUBTREE')
        logger.debug('search filter: %s' % _f)
        logger.debug('search attributes: %s' % ', '.join(search_attrs))

        allowed_senders = []
        try:
            qr = conn.search_s(dn_rcpt_domain, 2, _f, search_attrs)
            logger.debug('search result: %s' % repr(qr))

            # Collect values of all search attributes
            for (_dn, _ldif) in qr:
                for k in search_attrs:
                    allowed_senders += _ldif.get(k, [])

            if sender in allowed_senders:
                return SMTP_ACTIONS['default'] + ' (Sender bypasses access policy: %s (%s))' % (MAILLIST_POLICY_MEMBERSANDMODERATORSONLY, sender)
        except Exception, e:
            _msg = 'Error while querying allowed senders of mailing list (access policy: %s): %s' % (MAILLIST_POLICY_MEMBERSANDMODERATORSONLY, repr(e))
            logger.error(_msg)
            return SMTP_ACTIONS['default'] + ' (%s)' % _msg

        return SMTP_ACTIONS['reject_not_authorized']

    elif policy == MAILLIST_POLICY_MODERATORS:
        # If sender is hosted on local server, check per-user alias addresses
        # and alias domains.

        # Already checked `listAllowedUser` above before checking any access
        # policy, so it's safe to reject here..
        if not kwargs['sasl_username']:
            return SMTP_ACTIONS['reject_not_authorized']

        # Remove '*@domain.com'
        allowed_senders = [s for s in explicitly_allowed_senders if not s.startswith('*@')]

        # Separate email addresses and domain names
        _users = []
        _domains = []

        for _as in allowed_senders:
            if utils.is_email(_as):
                if _as.endswith('@' + recipient_domain):
                    _users.append(_as)

                    # We will add both `_as` and its shadowAddress back later.
                    allowed_senders.remove(_as)
            else:
                if _as.startswith('.'):
                    _domains.append(_as.lstrip('.'))
                else:
                    _domains.append(_as)

                # We will add both `_as` and its alias domains back later.
                allowed_senders.remove(_as)

        logger.debug('Allowed users: %s' % ', '.join(_users))
        logger.debug('Allowed domains: %s' % ', '.join(_domains))

        # Get per-user alias addresses.
        if _users:
            logger.debug("[+] Getting per-account alias addresses of allowed senders.")

            _basedn = 'ou=Users,' + dn_rcpt_domain
            _f = '(&(objectClass=mailUser)(enabledService=shadowaddress)(|'
            for i in _users:
                _f += '(mail=%s)(shadowAddress=%s)' % (i, i)
            _f += '))'

            _search_attrs = ['mail', 'shadowAddress']

            logger.debug('base dn: %s' % _basedn)
            logger.debug('search scope: ONELEVEL')
            logger.debug('search filter: %s' % _f)
            logger.debug('search attributes: %s' % ', '.join(search_attrs))

            qr = conn.search_s(_basedn, 1, _f, _search_attrs)
            logger.debug('query result: %s' % str(qr))

            for (_dn, _ldif) in qr:
                for k in _search_attrs:
                    allowed_senders += _ldif.get(k, [])

        if _domains:
            logger.debug('[+] Getting alias domains of allowed sender (sub-)domains.')

            _basedn = settings.ldap_basedn
            _f = '(&(objectClass=mailDomain)(enabledService=domainalias)(|'
            for i in _domains:
                _f += '(domainName=%s)(domainAliasName=%s)' % (i, i)
            _f += '))'

            _search_attrs = ['domainName', 'domainAliasName']

            logger.debug('base dn: %s' % _basedn)
            logger.debug('search scope: ONELEVEL')
            logger.debug('search filter: %s' % _f)
            logger.debug('search attributes: %s' % ', '.join(search_attrs))

            qr = conn.search_s(_basedn, 1, _f, _search_attrs)
            logger.debug('result: %s' % str(qr))

            for (_dn, _ldif) in qr:
                _all_domains = []
                for k in _search_attrs:
                    _all_domains += _ldif.get(k, [])

                for domain in _all_domains:
                    if domain in _domains:
                        # Add original domain and alias domains
                        allowed_senders += [d for d in _all_domains]

        if sender in allowed_senders or sender_domain in allowed_senders:
            return SMTP_ACTIONS['default'] + ' (Sender is allowed)'
        else:
            return SMTP_ACTIONS['reject_not_authorized']

    return SMTP_ACTIONS['default'] + ' (Unknown access policy: %s, no restriction)' % policy
