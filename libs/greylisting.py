from libs import utils

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
