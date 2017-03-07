# Author: Zhang Huangbin <zhb _at_ iredmail.org>

from libs.logger import logger
from libs import utils
import ldap
import settings

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


def get_primary_and_alias_domains(conn, domain):
    """Query LDAP to get all available alias domain names of given domain.

    Return list of alias domain names.

    @conn -- ldap connection cursor
    @domain -- domain name
    """
    if not utils.is_domain(domain):
        return []

    try:
        _f = "(&(objectClass=mailDomain)(|(domainName=%s)(domainAliasName=%s)))" % (domain, domain)
        qr = conn.search_s(settings.ldap_basedn,
                           1,  # 1 == ldap.SCOPE_ONELEVEL
                           _f,
                           ['domainName', 'domainAliasName'])
        if qr:
            (_dn, _ldif) = qr[0]
            _all_domains = _ldif.get('domainName', []) + _ldif.get('domainAliasName', [])

            return list(set(_all_domains))
    except Exception, e:
        # Log and return if LDAP error occurs
        logger.error('Error while querying alias domains of domain (%s): %s' % (domain, repr(e)))
        return []


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
