# Author: Zhang Huangbin <zhb _at_ iredmail.org>

from libs.logger import logger
from libs import utils
import ldap
import settings


def get_account_ldif(conn, account, query_filter=None, attrs=None):
    logger.debug(f"[+] Getting LDIF data of account: {account}")

    if not query_filter:
        query_filter = '(&' + \
                       '(!(domainStatus=disabled))' + \
                       '(|(mail=%(account)s)(shadowAddress=%(account)s))' % {'account': account} + \
                       '(|' + \
                       '(objectClass=mailUser)' + \
                       '(objectClass=mailList)' + \
                       '(objectClass=mailAlias)' + \
                       '))'

    logger.debug(f"search base dn: {settings.ldap_basedn}")
    logger.debug("search scope: SUBTREE")
    logger.debug(f"search filter: {query_filter}")
    logger.debug(f"search attributes: {attrs}")
    if not isinstance(attrs, list):
        # Attribute list must be None (search all attributes) or non-empty list
        attrs = None

    try:
        result = conn.search_s(settings.ldap_basedn,
                               ldap.SCOPE_SUBTREE,
                               query_filter,
                               attrs)

        if result:
            logger.debug(f"result: {repr(result)}")
            # (dn, entry = result[0])
            return result[0]
        else:
            logger.debug('No such account.')
            return (None, None)
    except Exception as e:
        logger.debug(f"<!> ERROR: {repr(e)}")
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
    except Exception as e:
        # Log and return if LDAP error occurs
        logger.error(f"Error while querying alias domains of domain ({domain}): {repr(e)}")
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
        _filter = '(&(objectClass=mailDomain)(accountStatus=active)'

        if include_alias_domain:
            _filter += '(|(domainName=%s)(domainAliasName=%s))' % (domain, domain)
        else:
            _filter += '(domainName=%s)' % domain

        if not include_backupmx:
            _filter += '(!(domainBackupMX=yes))'

        _filter += ')'

        qr = conn.search_s(settings.ldap_basedn,
                           1,   # 1 == ldap.SCOPE_ONELEVEL
                           _filter,
                           ['dn'])
        if qr:
            return True
    except ldap.NO_SUCH_OBJECT:
        return False
    except Exception as e:
        logger.error(f"<!> Error while querying local domain: {repr(e)}")
        return False


def get_alias_target_domain(alias_domain, conn, include_backupmx=True):
    """Query target domain of given alias domain name."""
    alias_domain = str(alias_domain).lower()

    if not utils.is_domain(alias_domain):
        logger.debug(f"Given alias_domain {alias_domain} is not an valid domain name.")
        return None

    try:
        _filter = '(&(objectClass=mailDomain)(accountStatus=active)'
        _filter += '(domainAliasName=%s)' % alias_domain

        if not include_backupmx:
            _filter += '(!(domainBackupMX=yes))'

        _filter += ')'

        logger.debug(f"[LDAP] query target domain of given alias domain ({alias_domain})")
        logger.debug(f"[LDAP] query filter: ({_filter})")
        qr = conn.search_s(settings.ldap_basedn,
                           1,   # 1 == ldap.SCOPE_ONELEVEL
                           _filter,
                           ['domainName'])

        logger.debug(f"result: {repr(qr)}")
        if qr:
            (_dn, _ldif) = qr[0]
            _domain = _ldif['domainName'][0]
            return _domain
    except ldap.NO_SUCH_OBJECT:
        pass
    except Exception as e:
        logger.error(f"<!> Error while querying alias domain: {repr(e)}")

    return None
