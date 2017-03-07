# Author: Zhang Huangbin <zhb _at_ iredmail.org>

from libs.logger import logger
from libs import utils
import ldap
import settings

from libs import MAILLIST_POLICY_MEMBERSONLY, MAILLIST_POLICY_ALLOWEDONLY
from libs import MAILLIST_POLICY_MEMBERSANDMODERATORSONLY


def get_account_ldif(conn, account, query_filter=None, attrs=None):
    logger.debug('[+] Getting LDIF data of account: %s' % account)

    if not query_filter:
        query_filter = '(&' + \
                       '(!(domainStatus=disabled))' + \
                       '(|(mail=%(account)s)(shadowAddress=%(account)s))' % {'account': account} + \
                       '(|' + \
                       '(objectClass=mailUser)' + \
                       '(objectClass=mailList)' + \
                       '(objectClass=mailAlias)' + \
                       '))'

    logger.debug('search base dn: %s' % settings.ldap_basedn)
    logger.debug('search scope: SUBTREE')
    logger.debug('search filter: %s' % query_filter)
    logger.debug('search attributes: %s' % str(attrs))
    if not isinstance(attrs, list):
        # Attribute list must be None (search all attributes) or non-empty list
        attrs = None

    try:
        result = conn.search_s(settings.ldap_basedn,
                               ldap.SCOPE_SUBTREE,
                               query_filter,
                               attrs)

        if result:
            logger.debug('result: %s' % str(result))
            # (dn, entry = result[0])
            return result[0]
        else:
            logger.debug('No such account.')
            return (None, None)
    except Exception, e:
        logger.debug('<!> ERROR, result: %s' % str(e))
        return (None, None)


def get_allowed_senders_of_mail_list(conn,
                                     sender,
                                     recipient,
                                     recipient_domain,
                                     policy,
                                     allowed_senders):
    """Return list of allowed senders.

    @conn -- ldap connection cursor
    @sender -- sender email address
    @recipient -- recipient email address
    @recipient -- recipient domain
    @policy -- access policy name of mailing list
    @allowed_senders -- a list of allowed senders
    """

    logger.debug('[+] Getting allowed senders of mail list: %s' % recipient)

    # Get domain dn.
    domaindn = 'domainName=' + recipient_domain + ',' + settings.ldap_basedn

    # Default base dn and search scope
    basedn = domaindn
    search_scope = 2    # 2 == ldap.SCOPE_SUBTREE

    # Replace 'allowedonly` by 'moderatorsonly'
    if policy == 'allowedonly':
        policy = 'moderatorsonly'

    # Set search filter, attributes based on policy.
    # Override base dn and search scope if necessary.
    if policy == MAILLIST_POLICY_MEMBERSONLY:
        # Filter: get mail list members.
        search_filter = '(&' + \
                        '(accountStatus=active)(memberOfGroup=%s)' % (recipient) + \
                        '(|(objectclass=mailUser)(objectClass=mailExternalUser))' + \
                        ')'

        # Get both mail and shadowAddress.
        search_attrs = ['mail', 'shadowAddress']
    elif policy == MAILLIST_POLICY_MEMBERSANDMODERATORSONLY:
        # Filter: get both members and moderators.
        search_filter = '(|' + \
                        '(&(memberOfGroup=%s)(|(objectClass=mailUser)(objectClass=mailExternalUser)))' % recipient + \
                        '(&(objectclass=mailList)(mail=%s))' % recipient + \
                        ')'
        search_attrs = ['mail', 'shadowAddress', 'listAllowedUser']

    if policy == MAILLIST_POLICY_ALLOWEDONLY:
        # Not necessary to query LDAP to get value of listAllowedUser.
        pass
    else:
        logger.debug('base dn: %s' % basedn)
        logger.debug('search scope: %s' % search_scope)
        logger.debug('search filter: %s' % search_filter)
        logger.debug('search attributes: %s' % ', '.join(search_attrs))

        allowed_senders = []
        try:
            qr = conn.search_s(basedn, search_scope, search_filter, search_attrs)
            logger.debug('search result: %s' % repr(qr))

            # Collect values of all search attributes
            for (_dn, _ldif) in qr:
                for k in search_attrs:
                    allowed_senders += _ldif.get(k, [])
        except Exception, e:
            logger.error('Error while querying allowed senders of mailing list: %s' % repr(e))
            return []

    logger.debug('query result: %s' % ', '.join(allowed_senders))

    if policy == MAILLIST_POLICY_ALLOWEDONLY:
        # Seperate valid email addresses under same domain and domain names.
        allowed_users = []
        allowed_domains = []
        allowed_subdomains = []

        for _allowed_sender in allowed_senders:
            if utils.is_email(_allowed_sender):
                if _allowed_sender.endswith('@' + recipient_domain):
                    allowed_users.append(_allowed_sender)

                    # We will add both `_allowed_sender` and its shadowAddress back later.
                    allowed_senders.remove(_allowed_sender)
            else:
                if _allowed_sender.startswith('.'):
                    allowed_subdomains.append(_allowed_sender.lstrip('.'))
                else:
                    allowed_domains.append(_allowed_sender)
                allowed_senders.remove(_allowed_sender)

        logger.debug('Allowed users: %s' % ', '.join(allowed_users))
        logger.debug('Allowed domains: %s' % ', '.join(allowed_domains))
        logger.debug('Allowed subdomains: %s' % ', '.join(allowed_subdomains))

        if allowed_users:
            logger.debug("[+] Getting per-account alias addresses of allowed senders.")

            basedn = 'ou=Users,' + domaindn
            search_filter = '(&(objectClass=mailUser)(enabledService=shadowaddress)(|'
            for i in allowed_users:
                search_filter += '(mail=%s)(shadowAddress=%s)' % (i, i)
            search_filter += '))'

            search_attrs = ['mail', 'shadowAddress']

            logger.debug('base dn: %s' % basedn)
            logger.debug('search scope: ONELEVEL')
            logger.debug('search filter: %s' % search_filter)
            logger.debug('search attributes: %s' % ', '.join(search_attrs))

            qr = conn.search_s(basedn, 1, search_filter, search_attrs)
            logger.debug('result: %s' % str(qr))

            for (_dn, _ldif) in qr:
                for k in search_attrs:
                    allowed_senders += _ldif.get(k, [])

        if allowed_domains or allowed_subdomains:
            logger.debug('[+] Getting alias domain names of allowed (sub-)domains.')

            basedn = settings.ldap_basedn
            search_filter = '(&(objectClass=mailDomain)(enabledService=domainalias)(|'
            for i in allowed_domains + allowed_subdomains:
                search_filter += '(domainName=%s)(domainAliasName=%s)' % (i, i)
            search_filter += '))'

            search_attrs = ['domainName', 'domainAliasName']

            logger.debug('base dn: %s' % basedn)
            logger.debug('search scope: ONELEVEL')
            logger.debug('search filter: %s' % search_filter)
            logger.debug('search attributes: %s' % ', '.join(search_attrs))

            qr = conn.search_s(basedn, 1, search_filter, search_attrs)
            logger.debug('result: %s' % str(qr))

            for (_dn, _ldif) in qr:
                domains = []
                for k in search_attrs:
                    domains += _ldif.get(k, [])

                for domain in domains:
                    if domain in allowed_domains:
                        # Add original domain and alias domains
                        allowed_senders += [d for d in domains]

                    if domain in allowed_subdomains:
                        # Add sub-domain and sub-domain of alias domains
                        allowed_senders += ['.' + d for d in domains]

    return [s.lower() for s in allowed_senders]


def is_local_domain(conn, domain):
    if not utils.is_domain(domain):
        return False

    if utils.is_server_hostname(domain):
        return True

    try:
        filter_domains = '(&(objectClass=mailDomain)'
        filter_domains += '(|(domainName=%s)(domainAliasName=%s))' % (domain, domain)
        filter_domains += ')'

        qr = conn.search_s(settings.ldap_basedn,
                           1,   # 1 == ldap.SCOPE_ONELEVEL
                           filter_domains,
                           ['dn'])
        if qr:
            return True
    except ldap.NO_SUCH_OBJECT:
        return False
    except Exception, e:
        logger.error('<!> Error while querying alias domain: %s' % str(e))
        return False
