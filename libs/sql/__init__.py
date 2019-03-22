from web import sqlquote

from libs.logger import logger
from libs import utils


def is_local_domain(conn,
                    domain,
                    include_alias_domain=True,
                    include_backupmx=True):
    """Check whether given domain name is hosted on localhost and not disabled.

    @conn -- SQL connection cursor
    @domain -- a domain name
    @include_backupmx -- whether we should include backup mx domain names in
                         query result.
    """
    if not utils.is_domain(domain):
        return False

    if utils.is_server_hostname(domain):
        return True

    try:
        sql_quote_domain = sqlquote(domain)

        # include backup mx domains by default.
        sql_backupmx = ''
        if not include_backupmx:
            sql_backupmx = 'AND backupmx=0'

        sql = """SELECT domain
                   FROM domain
                  WHERE domain=%s AND active=1 %s
                  LIMIT 1""" % (sql_quote_domain, sql_backupmx)
        logger.debug('[SQL] query local domain ({0}): \n{1}'.format(domain, sql))

        qr = conn.execute(sql)
        sql_record = qr.fetchone()
        logger.debug('SQL query result: %s' % str(sql_record))

        if sql_record:
            return True
    except Exception, e:
        logger.error('<!> Error while querying domain: {0}'.format(e))

    # Query alias domain
    try:
        if include_alias_domain:
            sql = """SELECT alias_domain.alias_domain
                       FROM alias_domain, domain
                      WHERE domain.active=1
                            AND domain.domain=alias_domain.target_domain
                            AND alias_domain.alias_domain=%s
                      LIMIT 1""" % sql_quote_domain

            logger.debug('[SQL] query alias domain ({0}): \n{1}'.format(domain, sql))

            qr = conn.execute(sql)
            sql_record = qr.fetchone()
            logger.debug('[SQL] query result: {0}'.format(sql_record))

            if sql_record:
                return True
    except Exception, e:
        logger.error('<!> Error while querying alias domain: {0}'.format(e))

    return False


def get_alias_target_domain(alias_domain, conn):
    """Query target domain of given alias domain name."""
    alias_domain = str(alias_domain).lower()
    if not utils.is_domain(alias_domain):
        logger.debug('Given alias domain ({0}) is not a valid domain name.'.format(alias_domain))
        return None

    sql = """SELECT alias_domain.target_domain
               FROM alias_domain, domain
              WHERE domain.active=1
                    AND domain.domain=alias_domain.target_domain
                    AND alias_domain.alias_domain=%s
              LIMIT 1""" % sqlquote(alias_domain)

    logger.debug('[SQL] query target domain of given alias domain ({0}): \n{1}'.format(alias_domain, sql))

    qr = conn.execute(sql)
    sql_record = qr.fetchone()
    logger.debug('[SQL] query result: {0}'.format(sql_record))

    if sql_record:
        target_domain = str(sql_record[0]).lower()
        return target_domain
    else:
        return None


def get_access_policy(mail, account_type, conn):
    """Get access policy of (mlmmj) mailing list or mail alias account.

    Returns access policy (string) or None if account doesn't exist."""
    _policy = None

    if account_type == 'alias':
        table = 'alias'
    elif account_type == 'maillist':
        table = 'maillists'
    else:
        return _policy

    sql = """SELECT accesspolicy
               FROM %s
              WHERE address=%s
              LIMIT 1""" % (table, sqlquote(mail))

    logger.debug('[SQL] query access policy: \n{0}'.format(sql))

    qr = conn.execute(sql)
    record = qr.fetchone()
    logger.debug('[SQL] query result: {0}'.format(record))

    if record:
        _policy = str(record[0]).lower()

    return _policy
