# Used by plugin: amavisd_wblist

from web import sqlquote
from libs import utils
from libs.logger import logger


def create_mailaddr(conn, addresses):
    for addr in addresses:
        addr_type = utils.is_valid_amavisd_address(addr)
        if addr_type in utils.MAILADDR_PRIORITIES:
            priority = utils.MAILADDR_PRIORITIES[addr_type]
            try:
                sql = "INSERT INTO mailaddr (email, priority) VALUES (%s, %s)" % (sqlquote(addr), sqlquote(priority))
                conn.execute(sql)
            except:
                pass

    return True


def create_user(conn, account, return_record=True):
    # Create a new record in `amavisd.users`
    addr_type = utils.is_valid_amavisd_address(account)
    try:
        # Use policy_id=0 to make sure it's not linked to any policy.
        sql = "INSERT INTO users (policy_id, email, priority) VALUES (%d, '%s', %d)" % (0, account, utils.MAILADDR_PRIORITIES[addr_type])
        conn.execute(sql)

        if return_record:
            sql = "SELECT id, priority, policy_id, email FROM users WHERE email='%s' LIMIT 1" % account
            qr = conn.execute(sql)
            sql_record = qr.fetchone()
            return (True, sql_record)
        else:
            return (True, )
    except Exception as e:
        return (False, str(e))


def get_user_record(conn, account, create_if_missing=True):
    try:
        sql = """SELECT id, priority, policy_id, email
                   FROM users
                  WHERE email='%s'
                  LIMIT 1""" % account
        qr = conn.execute(sql)
        sql_record = qr.fetchall()

        if sql_record:
            user_record = sql_record[0]
        else:
            if create_if_missing:
                qr = create_user(conn=conn,
                                 account=account,
                                 return_record=True)

                if qr[0]:
                    user_record = qr[1]
                else:
                    return qr
            else:
                return (False, 'ACCOUNT_NOT_EXIST')

        (_id, _priority, _policy_id, _email) = user_record

        d = {
            'id': int(_id),
            'priority': int(_priority),
            '_policy_id': int(_policy_id),
            'email': str(_email),
        }

        return (True, d)
    except Exception as e:
        return (False, str(e))


def add_wblist(conn,
               account,
               wl_senders=None,
               bl_senders=None,
               wl_rcpts=None,
               bl_rcpts=None,
               flush_before_import=False):
    """Add white/blacklists for specified account.

    wl_senders -- whitelist senders (inbound)
    bl_senders -- blacklist senders (inbound)
    wl_rcpts -- whitelist recipients (outbound)
    bl_rcpts -- blacklist recipients (outbound)
    flush_before_import -- Delete all existing wblist before importing
                           new wblist
    """
    if not utils.is_valid_amavisd_address(account):
        return (False, 'INVALID_ACCOUNT')

    # Remove duplicate.
    if wl_senders:
        wl_senders = set([str(s).lower()
                          for s in wl_senders
                          if utils.is_valid_amavisd_address(s)])
    else:
        wl_senders = set()

    # Whitelist has higher priority, don't include whitelisted sender.
    if bl_senders:
        bl_senders = set([str(s).lower()
                          for s in bl_senders
                          if utils.is_valid_amavisd_address(s)])
    else:
        bl_senders = set()

    if wl_rcpts:
        wl_rcpts = set([str(s).lower()
                        for s in wl_rcpts
                        if utils.is_valid_amavisd_address(s)])
    else:
        wl_rcpts = set()

    if bl_rcpts:
        bl_rcpts = set([str(s).lower()
                        for s in bl_rcpts
                        if utils.is_valid_amavisd_address(s)])
    else:
        bl_rcpts = set()

    if flush_before_import:
        if wl_senders:
            bl_senders = set([s for s in bl_senders if s not in wl_senders])

        if wl_rcpts:
            bl_rcpts = set([s for s in bl_rcpts if s not in wl_rcpts])

    sender_addresses = set(wl_senders) | set(bl_senders)
    rcpt_addresses = set(wl_rcpts) | set(bl_rcpts)
    all_addresses = list(sender_addresses | rcpt_addresses)

    # Get current user's id from `amavisd.users`
    qr = get_user_record(conn=conn, account=account)

    if qr[0]:
        user_id = qr[1]['id']
    else:
        return qr

    # Delete old records
    if flush_before_import:
        # user_id = wblist.rid
        conn.execute('DELETE FROM wblist WHERE rid=%s' % sqlquote(user_id))

        # user_id = outbound_wblist.sid
        conn.execute('DELETE FROM outbound_wblist WHERE sid=%s' % sqlquote(user_id))

    if not all_addresses:
        return (True, )

    # Insert all senders into `amavisd.mailaddr`
    create_mailaddr(conn=conn, addresses=all_addresses)

    # Get `mailaddr.id` of senders
    sender_records = {}
    if sender_addresses:
        sql = "SELECT id, email FROM mailaddr WHERE email IN %s" % sqlquote(list(sender_addresses))
        qr = conn.execute(sql)
        sql_records = qr.fetchall()
        for r in sql_records:
            (_id, _email) = r
            sender_records[_email.decode()] = int(_id)
        del qr

    # Get `mailaddr.id` of recipients
    rcpt_records = {}
    if rcpt_addresses:
        sql = "SELECT id, email FROM mailaddr WHERE email IN %s" % sqlquote(list(rcpt_addresses))
        qr = conn.execute(sql)
        sql_records = qr.fetchall()

        for r in sql_records:
            (_id, _email) = r
            rcpt_records[_email.decode()] = int(_id)
        del qr

    # Remove existing records of current submitted records then insert new.
    try:
        if sender_records:
            sql = "DELETE FROM wblist WHERE rid=%d AND sid IN %s" % (user_id, sqlquote(list(sender_records.values())))
            conn.execute(sql)

        if rcpt_records:
            sql = "DELETE FROM outbound_wblist WHERE sid=%d AND rid IN %s" % (user_id, sqlquote(list(rcpt_records.values())))
            conn.execute(sql)
    except Exception as e:
        return (False, e)

    # Generate dict used to build SQL statements for importing wblist
    values = []
    if sender_addresses:
        for s in wl_senders:
            if sender_records.get(s):
                values.append({'rid': user_id, 'sid': sender_records[s], 'wb': 'W'})

        for s in bl_senders:
            # Filter out same record in blacklist
            if sender_records.get(s) and s not in wl_senders:
                values.append({'rid': user_id, 'sid': sender_records[s], 'wb': 'B'})

    rcpt_values = []
    if rcpt_addresses:
        for s in wl_rcpts:
            if rcpt_records.get(s):
                rcpt_values.append({'sid': user_id, 'rid': rcpt_records[s], 'wb': 'W'})

        for s in bl_rcpts:
            # Filter out same record in blacklist
            if rcpt_records.get(s) and s not in wl_rcpts:
                rcpt_values.append({'sid': user_id, 'rid': rcpt_records[s], 'wb': 'B'})

    try:
        if values:
            for v in values:
                try:
                    conn.execute("INSERT INTO wblist (sid, rid, wb) VALUES (%s, %s, %s)" % (sqlquote(v['sid']),
                                                                                            sqlquote(v['rid']),
                                                                                            sqlquote(v['wb'])))
                except Exception as e:
                    logger.error(e)

        if rcpt_values:
            for v in rcpt_values:
                try:
                    conn.execute("INSERT INTO outbound_wblist (sid, rid, wb) VALUES (%s, %s, %s)" % (sqlquote(v['sid']),
                                                                                                     sqlquote(v['rid']),
                                                                                                     sqlquote(v['wb'])))
                except Exception as e:
                    logger.error(e)

    except Exception as e:
        return (False, e)

    return (True, )


def delete_wblist(conn,
                  account,
                  wl_senders=None,
                  bl_senders=None,
                  wl_rcpts=None,
                  bl_rcpts=None):
    if not utils.is_valid_amavisd_address(account):
        return (False, 'INVALID_ACCOUNT')

    # Remove duplicate.
    if wl_senders:
        wl_senders = list(set([str(s).lower()
                               for s in wl_senders
                               if utils.is_valid_amavisd_address(s)]))

    # Whitelist has higher priority, don't include whitelisted sender.
    if bl_senders:
        bl_senders = list(set([str(s).lower()
                               for s in bl_senders
                               if utils.is_valid_amavisd_address(s)]))

    if wl_rcpts:
        wl_rcpts = list(set([str(s).lower()
                             for s in wl_rcpts
                             if utils.is_valid_amavisd_address(s)]))

    if bl_rcpts:
        bl_rcpts = list(set([str(s).lower()
                             for s in bl_rcpts
                             if utils.is_valid_amavisd_address(s)]))

    # Get account id from `amavisd.users`
    qr = get_user_record(conn=conn, account=account)

    if qr[0]:
        user_id = qr[1]['id']
    else:
        return qr

    # Remove wblist.
    # No need to remove unused senders in `mailaddr` table, because we
    # have daily cron job to delete them (tools/cleanup_amavisd_db.py).
    wl_smails = []
    wl_rmails = []
    bl_smails = []
    bl_rmails = []
    try:
        # Get `mailaddr.id` for wblist senders
        if wl_senders:
            sids = []

            sql = "SELECT id, email FROM mailaddr WHERE email in %s" % sqlquote(wl_senders)
            qr = conn.execute(sql)
            sql_records = qr.fetchall()

            for r in sql_records:
                (_id, _email) = r
                sids.append(int(_id))
                wl_smails.append(str(_email))

            if sids:
                conn.execute("DELETE FROM wblist WHERE rid=%s AND sid IN %s AND wb='W'" % (sqlquote(user_id), sqlquote(sids)))

        if bl_senders:
            sids = []

            sql = "SELECT id, email FROM mailaddr WHERE email IN %s" % sqlquote(bl_senders)
            qr = conn.execute(sql)
            sql_records = qr.fetchall()

            for r in sql_records:
                (_id, _email) = r
                sids.append(int(_id))
                bl_smails.append(str(_email))

            if sids:
                conn.execute("DELETE FROM wblist WHERE rid=%s AND sid IN %s AND wb='B'" % (sqlquote(user_id), sqlquote(sids)))

        if wl_rcpts:
            rids = []

            sql = "SELECT id, email FROM mailaddr WHERE email IN %s" % sqlquote(wl_rcpts)
            qr = conn.execute(sql)
            sql_records = qr.fetchall()

            for r in sql_records:
                (_id, _email) = r
                rids.append(int(_id))
                wl_rmails.append(str(_email))

            if rids:
                conn.execute("DELETE FROM outbound_wblist WHERE sid=%s AND rid IN %s AND wb='W'" % (sqlquote(user_id), sqlquote(rids)))

        if bl_rcpts:
            rids = []

            sql = "SELECT id, email FROM mailaddr WHERE email IN %s" % sqlquote(bl_rcpts)
            qr = conn.execute(sql)
            sql_records = qr.fetchall()

            for r in sql_records:
                (_id, _email) = r
                rids.append(int(_id))
                bl_rmails.append(str(_email))

            if rids:
                conn.execute("DELETE FROM outbound_wblist WHERE sid=%s AND rid IN %s AND wb='B'" % (sqlquote(user_id), sqlquote(rids)))

    except Exception as e:
        return (False, str(e))

    return (True, {'wl_senders': wl_smails,
                   'wl_rcpts': wl_rmails,
                   'bl_senders': bl_smails,
                   'bl_rcpts': bl_rmails})


def delete_all_wblist(conn,
                      account,
                      wl_senders=False,
                      bl_senders=False,
                      wl_rcpts=False,
                      bl_rcpts=False):
    if not utils.is_valid_amavisd_address(account):
        return (False, 'INVALID_ACCOUNT')

    # Get account id from `amavisd.users`
    qr = get_user_record(conn=conn, account=account)

    if qr[0]:
        user_id = qr[1]['id']
    else:
        return qr

    # Remove ALL wblist.
    # No need to remove unused senders in `mailaddr` table, because we
    # have daily cron job to delete them (tools/cleanup_amavisd_db.py).
    try:
        if wl_senders:
            sql = "DELETE FROM wblist WHERE rid=%d AND wb='W'" % int(user_id)
            conn.execute(sql)

        if bl_senders:
            sql = "DELETE FROM wblist WHERE rid=%d AND wb='B'" % int(user_id)
            conn.execute(sql)

        if wl_rcpts:
            sql = "DELETE FROM outbound_wblist WHERE sid=%d AND wb='W'" % int(user_id)
            conn.execute(sql)

        if bl_rcpts:
            sql = "DELETE FROM outbound_wblist WHERE sid=%d AND wb='B'" % int(user_id)
            conn.execute(sql)
    except Exception as e:
        return (False, str(e))

    return (True, )


def get_account_wblist(conn,
                       account,
                       whitelist=True,
                       blacklist=True):
    """Get inbound white/blacklists of specified account."""
    sql_where = "users.email=%s AND users.id=wblist.rid AND wblist.sid = mailaddr.id" % sqlquote(account)
    if whitelist and not blacklist:
        sql_where += " AND wblist.wb='W'"

    if not whitelist and blacklist:
        sql_where += " AND wblist.wb='B'"

    wl = []
    bl = []

    try:
        sql = """SELECT mailaddr.email, wblist.wb
                   FROM mailaddr, users, wblist
                  WHERE %s
                  """ % sql_where
        qr = conn.execute(sql)
        sql_records = qr.fetchall()

        for r in sql_records:
            (_addr, _wb) = r
            if _wb == 'W':
                wl.append(_addr)
            else:
                bl.append(_addr)
    except Exception as e:
        return (False, e)

    return (True, {'whitelist': wl, 'blacklist': bl})


def get_account_outbound_wblist(conn,
                                account,
                                whitelist=True,
                                blacklist=True):
    """Get outbound white/blacklists of specified account."""
    sql_where = 'users.email=%s AND users.id=outbound_wblist.sid AND outbound_wblist.rid = mailaddr.id' % sqlquote(account)
    if whitelist and not blacklist:
        sql_where += " AND outbound_wblist.wb='W'"

    if not whitelist and blacklist:
        sql_where += " AND outbound_wblist.wb='B'"

    wl = []
    bl = []

    try:
        sql = """SELECT mailaddr.email, outbound_wblist.wb
                   FROM mailaddr, users, outbound_wblist
                  WHERE %s""" % sql_where
        qr = conn.execute(sql)
        sql_records = qr.fetchall()

        for r in sql_records:
            (_addr, _wb) = r
            if _wb == 'W':
                wl.append(_addr)
            else:
                bl.append(_addr)
    except Exception as e:
        return (False, e)

    return (True, {'whitelist': wl, 'blacklist': bl})
