from libs.logger import logger
from libs import utils


# TODO [?] No need to verify accounts in plugin, libs/xxx/modeler.py
#      already handle it.
# TODO query all: '@.', '@domain.com', '@.domain.com', 'user@domain.com'
# sort by priority ASC
def get_applicable_policy(db_cursor,
                          account,
                          policy_columns=['policy_name', 'message_size_limit'],
                          **kwargs):
    logger.debug('Getting applicable policies')
    account = str(account).lower()

    if utils.is_valid_amavisd_address(account) != 'email':
        # Postfix should use full email address as recipient.
        logger.debug('Policy account is not an email address.')
        return (True, {})

    sql_valid_rcpts = """'%s', '%s', '%s', '%s'""" % (
        account,                            # full email address
        '@' + kwargs['recipient_domain'],   # entire domain
        '@.' + kwargs['recipient_domain'],  # sub-domain
        '@.')                               # catch-all

    logger.debug('Valid policy accounts for recipient %s: %s' % (account, sql_valid_rcpts))
    try:
        sql = """SELECT %s
                 FROM users, policy
                 WHERE
                    (users.policy_id=policy.id)
                    AND (users.email IN (%s))
                 ORDER BY users.priority DESC
                 """ % (','.join(policy_columns), sql_valid_rcpts)
        logger.debug(sql)

        qr = db_cursor.execute(sql)
        records = qr.fetchmany(4)

        if records:
            return (True, records)
        else:
            return (True, {})
    except Exception, e:
        logger.debug('Error while quering Amavisd policy (%s): %s' % (account, str(e)))
        return (False, str(e))
