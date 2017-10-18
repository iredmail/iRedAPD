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


def is_local_domain(conn,
                    domain,
                    include_alias_domain=True,
                    include_backupmx=True):
    if not utils.is_domain(domain):
        return False

    if utils.is_server_hostname(domain):
        return True

    try:
        filter_domains = '(&(objectClass=mailDomain)(accountStatus=active)'

        if include_alias_domain:
            filter_domains += '(|(domainName=%s)(domainAliasName=%s))' % (domain, domain)
        else:
            filter_domains += '(domainName=%s)' % domain

        if not include_backupmx:
            filter_domains += '(!(domainBackupMX=yes))'

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


def get_alias_target_domain(alias_domain, conn, include_backupmx=True):
    """Query target domain of given alias domain name."""
    alias_domain = str(alias_domain).lower()
    if not utils.is_domain(alias_domain):
        logger.debug('Given alias_domain %s is not an valid domain name.' % alias_domain)
        return None

    try:
        _filter = '(&(objectClass=mailDomain)(accountStatus=active)'
        _filter += '(domainAliasName=%s)'

        if not include_backupmx:
            _filter += '(!(domainBackupMX=yes))'

        _filter += ')'

        logger.debug('[LDAP] query target domain of given alias domain (%s).' % alias_domain)
        qr = conn.search_s(settings.ldap_basedn,
                           1,   # 1 == ldap.SCOPE_ONELEVEL
                           _filter,
                           ['domainName'])

        if qr:
            logger.debug('result: %s' % str(qr))
            (_dn, _ldif) = qr[0]
            _domain = _ldif['domainName'][0]
            return _domain
    except ldap.NO_SUCH_OBJECT:
        pass
    except Exception, e:
        logger.error('<!> Error while querying alias domain: %s' % str(e))

    return None
