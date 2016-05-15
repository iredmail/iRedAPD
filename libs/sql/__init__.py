from libs.logger import logger
from libs import utils

def is_local_domain(conn, domain):
    if not utils.is_domain(domain):
        return False

    if utils.is_server_hostname(domain):
        return True

    try:
        sql = """SELECT alias_domain
                   FROM alias_domain
                  WHERE alias_domain='%s' OR target_domain='%s'
                  LIMIT 1""" % (domain, domain)
        logger.debug('[SQL] query alias domains: \n%s' % sql)

        qr = conn.execute(sql)
        sql_record = qr.fetchone()
        logger.debug('SQL query result: %s' % str(sql_record))

        if sql_record:
            return True
    except Exception, e:
        logger.error('<!> Error while querying alias domain: %s' % str(e))

    return False
