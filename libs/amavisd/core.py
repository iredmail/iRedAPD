import logging
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
    elif utils.is_email(addr):
        # single email address
        return 'email'
    elif utils.is_wildcard_addr(addr):
        return 'wildcard_addr'
    elif utils.is_strict_ip(addr):
        return 'ip'

    return False


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

        qr = db_cursor.execute(sql)
        records = qr.fetchmany(4)

        if records:
            return (True, records)
        else:
            return (True, {})
    except Exception, e:
        logging.debug('Error while quering Amavisd policy (%s): %s' % (account, str(e)))
        return (False, str(e))
