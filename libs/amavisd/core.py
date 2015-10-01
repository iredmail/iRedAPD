from libs.logger import logger
from libs import utils


def get_valid_addresses_from_email(email):
    # Return list valid Amavisd senders/recipients from an email address
    # - Sample user: user@sub2.sub1.com.cn
    # - Valid Amavisd senders:
    #   -> user@sub2.sub1.com.cn
    #   -> @sub2.sub1.com.cn
    #   -> @.sub2.sub1.com.cn
    #   -> @.sub1.com.cn
    #   -> @.com.cn
    #   -> @.cn
    (username, email_domain) = email.split('@', 1)
    splited_domain_parts = email_domain.split('.')

    # Default senders (user@domain.ltd):
    # ['@.', 'user@domain.ltd', @domain.ltd']
    valid_addresses = ['@.', email]
    for counter in range(len(splited_domain_parts)):
        # Append domain and sub-domain.
        subd = '.'.join(splited_domain_parts)
        valid_addresses += ['@' + subd, '@.' + subd]
        splited_domain_parts.pop(0)

    return valid_addresses


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
