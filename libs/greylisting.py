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
        conn.delete('greylisting',
                    vars={'account': account, 'sender': sender},
                    where='account = $account AND sender = $sender')

        return (True, )
    except Exception, e:
        return (False, str(e))

def enable_greylisting(conn, account, sender):
    gl_setting = get_gl_base_setting(account=account, sender=sender)

    try:
        # Delete existing setting first.
        delete_setting(conn=conn, account=account, sender=sender)

        gl_setting['active'] = 1
        conn.insert('greylisting', **gl_setting)

        return (True, )
    except Exception, e:
        return (False, str(e))

def disable_greylisting(conn, account, sender):
    gl_setting = get_gl_base_setting(account=account, sender=sender)

    try:
        # Delete existing setting first.
        delete_setting(conn=conn, account=account, sender=sender)

        gl_setting['active'] = 0
        conn.insert('greylisting', **gl_setting)

        return (True, )
    except Exception, e:
        return (False, str(e))
