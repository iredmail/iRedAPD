# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
import ldap
import settings
from libs import MAILLIST_POLICY_MEMBERSONLY, \
    MAILLIST_POLICY_ALLOWEDONLY, \
    MAILLIST_POLICY_MEMBERSANDMODERATORSONLY


def get_account_ldif(conn, account, query_filter=None, attrs=None):
    logging.debug('[+] Getting LDIF data of account: %s' % account)

    if not query_filter:
        query_filter = '(&' + \
                       '(|(mail=%(account)s)(shadowAddress=%(account)s))' % {'account': account} + \
                       '(|' + \
                       '(objectClass=mailUser)' + \
                       '(objectClass=mailList)' + \
                       '(objectClass=mailAlias)' + \
                       '))'

    logging.debug('search base dn: %s' % settings.ldap_basedn)
    logging.debug('search scope: SUBTREE')
    logging.debug('search filter: %s' % query_filter)
    logging.debug('search attributes: %s' % str(attrs))
    if not isinstance(attrs, list):
        # Attribute list must be None (search all attributes) or non-empty list
        attrs = None

    try:
        result = conn.search_s(settings.ldap_basedn,
                               ldap.SCOPE_SUBTREE,
                               query_filter,
                               attrs)

        if result:
            logging.debug('result: %s' % str(result))
            # (dn, entry = result[0])
            return result[0]
        else:
            logging.debug('No such account.')
            return (None, None)
    except Exception, e:
        logging.debug('<!> ERROR, result: %s' % str(e))
        return (None, None)


def get_allowed_senders_of_mail_list(conn,
                                     dn_of_mail_list,
                                     sender,
                                     recipient,
                                     policy,
                                     allowed_senders=[]):
    """return list of allowed senders"""

    logging.debug('[+] Getting allowed senders of mail list: %s' % recipient)

    # Get domain dn
    domaindn = dn_of_mail_list.split('ou=Groups,')[-1]

    # Default base dn and search scope (2==ldap.SCOPE_SUBTREE)
    basedn = domaindn
    search_scope = 2

    # Set search filter, attributes based on policy.
    # Override base dn, scope if necessary.
    if policy == MAILLIST_POLICY_MEMBERSONLY:
        # Filter: get mail list members.
        search_filter = '(&' + \
                        '(accountStatus=active)(memberOfGroup=%s)' % (recipient) + \
                        '(|(objectclass=mailUser)(objectClass=mailExternalUser))' + \
                        ')'

        # Get both mail and shadowAddress.
        search_attrs = ['mail', 'shadowAddress', ]
    elif policy == MAILLIST_POLICY_MEMBERSANDMODERATORSONLY:
        # Policy: policy==
        # Filter used to get both members and moderators.
        search_filter = "(|(&(|(objectClass=mailUser)(objectClass=mailExternalUser))(memberOfGroup=%s))(&(objectclass=mailList)(mail=%s)))" % (recipient, recipient)
        search_attrs = ['mail', 'shadowAddress', 'listAllowedUser']

    if policy == MAILLIST_POLICY_ALLOWEDONLY:
        # Not necessary to query LDAP to get value of listAllowedUser.
        allowed_senders = allowed_senders
    else:
        logging.debug('base dn: %s' % basedn)
        logging.debug('search scope: %s' % search_scope)
        logging.debug('search filter: %s' % search_filter)
        logging.debug('search attributes: %s' % ', '.join(search_attrs))

        allowed_senders = []
        try:
            qr = conn.search_s(basedn, search_scope, search_filter, search_attrs)
            logging.debug('search result: %s' % str(qr))

            # Collect all values
            for obj in qr:
                for k in search_attrs:
                    allowed_senders += obj[1].get(k, [])
        except Exception, e:
            logging.debug('Error: %s' % str(e))
            return []

    logging.debug('result: %s' % str(allowed_senders))

    if policy == MAILLIST_POLICY_ALLOWEDONLY:
        recipient_domain = recipient.split('@', 1)[-1]

        # Seperate valid email addresses under same domain and domain names.
        allowed_users = []
        allowed_domains = []
        allowed_subdomains = []

        for sender in allowed_senders:
            if '@' in sender:
                if sender.endswith('@' + recipient_domain):
                    allowed_users.append(sender)
                    # We will add both `sender` and its shadowAddress back later.
                    allowed_senders.remove(sender)
            else:
                if sender.startswith('.'):
                    allowed_subdomains.append(sender.lstrip('.'))
                else:
                    allowed_domains.append(sender)
                allowed_senders.remove(sender)

        logging.debug('Allowed users: %s' % ', '.join(allowed_users))
        logging.debug('Allowed domains: %s' % ', '.join(allowed_domains))
        logging.debug('Allowed subdomains: %s' % ', '.join(allowed_subdomains))

        if allowed_users:
            logging.debug("[+] Getting allowed senders' alias addresses.")

            basedn = 'ou=Users,' + domaindn
            search_filter = '(&(objectClass=mailUser)(enabledService=shadowaddress)(|'
            for i in allowed_users:
                search_filter += '(mail=%s)(shadowAddress=%s)' % (i, i)
            search_filter += '))'

            search_attrs = ['mail', 'shadowAddress']

            logging.debug('base dn: %s' % basedn)
            logging.debug('search scope: ONELEVEL')
            logging.debug('search filter: %s' % search_filter)
            logging.debug('search attributes: %s' % ', '.join(search_attrs))

            qr = conn.search_s(basedn, 1, search_filter, search_attrs)
            logging.debug('result: %s' % str(qr))

            for obj in qr:
                for k in search_attrs:
                    allowed_senders += obj[1].get(k, [])

        if allowed_domains or allowed_subdomains:
            logging.debug('Query to get domain aliases of allowed (sub-)domains.')

            basedn = settings.ldap_basedn
            search_filter = '(&(objectClass=mailDomain)(enabledService=domainalias)(|'
            for i in allowed_domains + allowed_subdomains:
                search_filter += '(domainName=%s)(domainAliasName=%s)' % (i, i)
            search_filter += '))'

            search_attrs = ['domainName', 'domainAliasName']

            logging.debug('base dn: %s' % basedn)
            logging.debug('search scope: ONELEVEL')
            logging.debug('search filter: %s' % search_filter)
            logging.debug('search attributes: %s' % ', '.join(search_attrs))

            qr = conn.search_s(basedn, 1, search_filter, search_attrs)
            logging.debug('result: %s' % str(qr))

            for obj in qr:
                domains = []
                for k in search_attrs:
                    domains += obj[1].get(k, [])

                for domain in domains:
                    if domain in allowed_domains:
                        # Add original domain and alias domains
                        allowed_senders += [d for d in domains]

                    if domain in allowed_subdomains:
                        # Add sub-domain and sub-domain of alias domains
                        allowed_senders += ['.' + d for d in domains]

    return [u.lower() for u in allowed_senders]
