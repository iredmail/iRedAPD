# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
import ldap
import settings


def get_account_ldif(conn, account, attrlist=None):
    logging.debug('[+] Getting LDIF data of account: %s' % account)

    query_filter = '(&' + \
                   '(|(mail=%(account)s)(shadowAddress=%(account)s))' + \
                   '(|' + \
                   '(objectClass=mailUser)' + \
                   '(objectClass=mailList)' + \
                   '(objectClass=mailAlias)' + \
                   '))' % {'account': account}

    logging.debug('query filter: %s' % query_filter)
    logging.debug('query attributes: %s' % str(attrlist))
    if not isinstance(attrlist, list):
        # Attribute list must be None or non-empty list
        attrlist = None

    try:
        result = conn.search_s(settings.ldap_basedn,
                               ldap.SCOPE_SUBTREE,
                               query_filter,
                               attrlist)

        if len(result) == 1:
            logging.debug('result: %s' % str(result))
            dn, entry = result[0]
            return (dn, entry)
        else:
            logging.debug('Not a local account.')
            return (None, None)
    except Exception, e:
        logging.debug('<!> ERROR, result: %s' % str(e))
        return (None, None)


def get_allowed_senders_of_mail_list(conn,
                                     base_dn,
                                     dn_of_mail_list,
                                     sender,
                                     recipient,
                                     policy):
    """return list of allowed senders"""

    logging.debug('[+] Getting allowed senders of mail list: %s' % recipient)
    recipient_domain = recipient.split('@', 1)[-1]

    # Set base dn as domain dn.
    domaindn = 'domainName=' + recipient_domain + ',' + base_dn

    # Default search scope. 2==ldap.SCOPE_SUBTREE
    searchScope = 2

    # Set search filter, attributes based on policy.
    # Override base dn, scope if necessary.
    if policy in ['membersonly', 'members']:
        basedn = domaindn
        # Filter: get mail list members.
        searchFilter = '(&(|(objectclass=mailUser)(objectClass=mailExternalUser))(accountStatus=active)(memberOfGroup=%s))' % (recipient)

        # Get both mail and shadowAddress.
        searchAttrs = ['mail', 'shadowAddress', ]

    elif policy in ['allowedonly', 'moderatorsonly', 'moderators']:
        # Get mail list moderators.
        basedn = dn_of_mail_list
        searchScope = 0     # Use ldap.SCOPE_BASE to improve performance.
        searchFilter = "(&(objectclass=mailList)(mail=%s))" % (recipient, )
        searchAttrs = ['listAllowedUser']

    else:
        basedn = domaindn
        # Policy: policy==membersAndModeratorsOnly or not set.
        # Filter used to get both members and moderators.
        searchFilter = "(|(&(|(objectClass=mailUser)(objectClass=mailExternalUser))(memberOfGroup=%s))(&(objectclass=mailList)(mail=%s)))" % (recipient, recipient, )
        searchAttrs = ['mail', 'shadowAddress', 'listAllowedUser', ]

    logging.debug('base dn: %s' % basedn)
    logging.debug('search scope: %s' % searchScope)
    logging.debug('search filter: %s' % searchFilter)
    logging.debug('search attributes: %s' % ', '.join(searchAttrs))

    try:
        result = conn.search_s(basedn, searchScope, searchFilter, searchAttrs)
        userList = []
        for obj in result:
            for k in searchAttrs:
                if k in obj[1].keys():
                    # Example of result data:
                    # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
                    userList += obj[1][k]

        # Exclude mail list itself.
        if recipient in userList:
            userList.remove(recipient)

        logging.debug('result: %s' % str(userList))

        # Query once more to get 'shadowAddress'.
        if len(userList) > 0 and policy in ['allowedonly',
                                            'moderatorsonly',
                                            'moderators']:
            logging.debug('Addition query to get user aliases...')

            basedn = 'ou=Users,' + domaindn
            searchFilter = '(&(objectClass=mailUser)(enabledService=shadowaddress)(|'
            for i in userList:
                searchFilter += '(mail=%s)' % i
            searchFilter += '))'

            searchAttrs = ['shadowAddress', ]

            logging.debug('base dn: %s' % basedn)
            logging.debug('search scope: 2 (ldap.SCOPE_SUBTREE)')
            logging.debug('search filter: %s' % searchFilter)
            logging.debug('search attributes: %s' % ', '.join(searchAttrs))

            try:
                resultOfShadowAddresses = conn.search_s(
                    'ou=Users,' + domaindn,
                    2,  # ldap.SCOPE_SUBTREE
                    searchFilter,
                    ['mail', 'shadowAddress', ],
                )

                for obj in resultOfShadowAddresses:
                    for k in searchAttrs:
                        if k in obj[1].keys():
                            # Example of result data:
                            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
                            userList += obj[1][k]
                        else:
                            pass

                logging.debug('final result: %s' % str(userList))

            except Exception, e:
                logging.debug('Error: %s' % str(e))

        return [u.lower() for u in userList]
    except Exception, e:
        logging.debug('Error: %s' % str(e))
        return []
