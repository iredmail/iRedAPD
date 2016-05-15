from libs import utils

def is_valid_sender(sender):
    if utils.is_ip(sender) or \
       utils.is_valid_amavisd_address(sender) in ['catchall',
                                                  'top_level_domain',
                                                  'domain', 'subdomain',
                                                  'email']:
        return True
    else:
        return False

def get_gl_base_setting(account, sender):
    return {'account': account,
            'priority': utils.get_account_priority(account),
            'sender': sender,
            'sender_priority': utils.get_account_priority(sender)}

def delete_setting(conn, account, sender):
    try:
        # Delete existing record first.
        sql_vars = {'account': account, 'sender': sender}
        sql = """DELETE FROM greylisting WHERE account='%(account)s'
                                           AND sender='%(sender)s'""" % sql_vars

        conn.execute(sql)

        return (True, )
    except Exception, e:
        return (False, str(e))

def enable_greylisting(conn, account, sender):
    gl_setting = get_gl_base_setting(account=account, sender=sender)

    try:
        # Delete existing setting first.
        delete_setting(conn=conn, account=account, sender=sender)
        gl_setting['active'] = 1

        sql = """INSERT INTO greylisting (account, priority, sender, sender_priority, active)
                                  VALUES (%(account)s, %(priority)d,
                                          %(sender)s, %(sender_priority)d,
                                          %(active)d)""" % gl_setting
        conn.execute(sql)

        return (True, )
    except Exception, e:
        return (False, str(e))

def disable_greylisting(conn, account, sender):
    gl_setting = get_gl_base_setting(account=account, sender=sender)
    gl_setting['active'] = 0

    try:
        # Delete existing setting first.
        delete_setting(conn=conn, account=account, sender=sender)

        sql = """INSERT INTO greylisting (account, priority, sender, sender_priority, active)
                                  VALUES (%(account)s, %(priority)d,
                                          %(sender)s, %(sender_priority)d,
                                          %(active)d)""" % gl_setting
        conn.execute(sql)

        return (True, )
    except Exception, e:
        return (False, str(e))

def add_whitelist_domain(conn, domain):
    # Insert domain into sql table `iredapd.greylisting_whitelist_domains`
    if not utils.is_domain(domain):
        return (False, 'INVALID_DOMAIN')

    try:
        sql = """INSERT INTO greylisting_whitelist_domains (domain) VALUES ('%s')""" % domain
        conn.execute(sql)
    except Exception, e:
        error = str(e).lower()
        if 'duplicate key' in error or 'duplicate entry' in error:
            pass
        else:
            return (False, str(e))

    return (True, )

def delete_whitelist_domain(conn, domain):
    # Insert domain into sql table `iredapd.greylisting_whitelist_domains`
    if not utils.is_domain(domain):
        return (False, 'INVALID_DOMAIN')

    try:
        sql = """DELETE FROM greylisting_whitelist_domains WHERE domain='%s'""" % domain
        conn.execute(sql)

        sql = """DELETE FROM greylisting_whitelists WHERE COMMENT='AUTO-UPDATE: %s'""" % domain
        conn.execute(sql)
    except Exception, e:
        error = str(e).lower()
        if 'duplicate key' in error or 'duplicate entry' in error:
            pass
        else:
            return (False, str(e))

    return (True, )
