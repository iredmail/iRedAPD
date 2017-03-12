from web import sqlquote

from libs.logger import logger
from libs import utils

def is_local_domain(conn, domain, include_backupmx=True):
    """Check whether given domain name is hosted on localhost.

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
                  WHERE domain=%s %s
                  LIMIT 1""" % (sql_quote_domain, sql_backupmx)
        logger.debug('[SQL] query local domain (%s): \n%s' % (domain, sql))

        qr = conn.execute(sql)
        sql_record = qr.fetchone()
        logger.debug('SQL query result: %s' % str(sql_record))

        if sql_record:
            return True

        sql = """SELECT alias_domain
                   FROM alias_domain
                  WHERE alias_domain=%s OR target_domain=%s
                  LIMIT 1""" % (sql_quote_domain, sql_quote_domain)
        logger.debug('[SQL] query alias domains (%s): \n%s' % (domain, sql))

        qr = conn.execute(sql)
        sql_record = qr.fetchone()
        logger.debug('SQL query result: %s' % str(sql_record))

        if sql_record:
            return True
    except Exception, e:
        logger.error('<!> Error while querying alias domain: %s' % str(e))

    return False
