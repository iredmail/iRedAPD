import logging
import settings
from libs import SMTP_ACTIONS, utils


def is_valid_amavisd_address(addr):
    # Valid address format:
    #   - email: single address. e.g. user@domain.ltd
    #   - domain: @domain.ltd
    #   - subdomain: entire domain and all sub-domains. e.g. @.domain.ltd
    #   - catch-all: catch all address. @.
    if addr.startswith(r'@.'):
        if addr == r'@.':
            # catch all
            return 'catchall'
        else:
            # sub-domains
            domain = addr.split(r'@.', 1)[-1]
            if utils.is_domain(domain):
                return 'subdomain'
    elif addr.startswith(r'@'):
        # entire domain
        domain = addr.split(r'@', 1)[-1]
        if utils.is_domain(domain):
            return 'domain'
    else:
        # single email address
        if utils.is_email(addr):
            return 'email'

    return False


# TODO [?] No need to verify accounts in plugin, libs/xxx/modeler.py
#      already handle it.
# TODO query all: '@.', '@domain.com', '@.domain.com', 'user@domain.com'
# sort by priority ASC
def get_applicable_policy(db_cursor,
                          account,
                          policy_columns=['policy_name', 'message_size_limit'],
                          **kwargs):
    logging.debug('Getting applicable policies')
    account = str(account).lower()

    addr_type = is_valid_amavisd_address(account)
    if addr_type == 'email':
        sql_valid_rcpts = """'%s', '%s', '%s', '%s'""" % (
            account,                            # full email address
            '@' + kwargs['recipient_domain'],   # entire domain
            '@.' + kwargs['recipient_domain'],  # sub-domain
            '@.')                               # catch-all
    else:
        # Postfix should use full email address as recipient.
        logging.debug('Policy account is not an email address.')
        return SMTP_ACTIONS['default']

    logging.debug('Valid policy accounts for recipient %s: %s' % (account, sql_valid_rcpts))
    try:
        sql = """SELECT %s
                 FROM users, policy
                 WHERE
                    (users.policy_id=policy.id)
                    AND (users.email IN (%s))
                 ORDER BY users.priority DESC
                 """ % (','.join(policy_columns), sql_valid_rcpts)
        logging.debug(sql)

        db_cursor.execute(sql)
        records = db_cursor.fetchmany(4)

        if records:
            return (True, records)
        else:
            return (True, {})
    except Exception, e:
        logging.debug('Error while quering Amavisd policy (%s): %s' % (account, str(e)))
        return (False, str(e))

class AmavisdDBWrap:
    def __init__(self):
        logging.debug('Creating Amavisd database connection.')

        if settings.amavisd_db_type == 'mysql':
            import MySQLdb
            try:
                db = MySQLdb.connect(host=settings.amavisd_db_server,
                                     port=int(settings.amavisd_db_port),
                                     db=settings.amavisd_db_name,
                                     user=settings.amavisd_db_user,
                                     passwd=settings.amavisd_db_password)
                self.cursor = db.cursor()
            except Exception, e:
                logging.debug("Error while creating Amavisd database connection: %s" % str(e))
        elif settings.backend == 'pgsql':
            import psycopg2
            try:
                db = psycopg2.connect(host=settings.sql_server,
                                      port=int(settings.sql_port),
                                      database=settings.sql_db,
                                      user=settings.sql_user,
                                      password=settings.sql_password)
                self.cursor = db.cursor()
            except Exception, e:
                logging.error("Error while creating Amavisd database connection: %s" % str(e))
        else:
            return SMTP_ACTIONS['default']

    def __del__(self):
        try:
            self.cursor.close()
            logging.debug('Closed Amavisd database connection.')
        except Exception, e:
            logging.debug('Error while closing Amavisd database connection: %s' % str(e))
