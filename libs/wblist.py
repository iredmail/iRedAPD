# Used by plugin: amavisd_wblist

from web import sqlquote
from libs import utils

def create_mailaddr(conn, addresses):
    for addr in addresses:
        addr_type = utils.is_valid_amavisd_address(addr)
        if addr_type in utils.MAILADDR_PRIORITIES:
            try:
                conn.insert('mailaddr',
                            priority=utils.MAILADDR_PRIORITIES[addr_type],
                            email=addr)
            except:
                pass

    return True


def create_user(conn, account, policy_id=0, return_record=True):
    # Create a new record in `amavisd.users`
    addr_type = utils.is_valid_amavisd_address(account)
    try:
        # Use policy_id=0 to make sure it's not linked to any policy.
        conn.insert('users',
                    policy_id=0,
                    email=account,
                    priority=utils.MAILADDR_PRIORITIES[addr_type])

        if return_record:
            qr = conn.select('users',
                             vars={'account': account},
                             what='*',
                             where='email=$account',
                             limit=1)
            return (True, qr[0])
        else:
            return (True, )
    except Exception, e:
        return (False, str(e))


def get_user_record(conn, account, create_if_missing=True):
    try:
        qr = conn.select('users',
                         vars={'email': account},
                         what='*',
                         where='email=$email',
                         limit=1)

        if qr:
            return (True, qr[0])
        else:
            if create_if_missing:
                qr = create_user(conn=conn,
                                 account=account,
                                 return_record=True)

                if qr[0]:
                    return (True, qr[1])
                else:
                    return qr
            else:
                (False, 'ACCOUNT_NOT_EXIST')
    except Exception, e:
        return (False, str(e))


def add_wblist(conn,
               account,
               wl_senders=(),
               bl_senders=(),
               wl_rcpts=(),
               bl_rcpts=(),
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

    # Whitelist has higher priority, don't include whitelisted sender.
    if bl_senders:
        bl_senders = set([str(s).lower()
                          for s in bl_senders
                          if utils.is_valid_amavisd_address(s)])

    if wl_rcpts:
        wl_rcpts = set([str(s).lower()
                        for s in wl_rcpts
                        if utils.is_valid_amavisd_address(s)])

    if bl_rcpts:
        bl_rcpts = set([str(s).lower()
                        for s in bl_rcpts
                        if utils.is_valid_amavisd_address(s)])

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
        user_id = qr[1].id
    else:
        return qr

    # Delete old records
    if flush_before_import:
        # user_id = wblist.rid
        conn.delete('wblist',
                    vars={'rid': user_id},
                    where='rid=$rid')

        # user_id = outbound_wblist.sid
        conn.delete('outbound_wblist',
                    vars={'sid': user_id},
                    where='sid=$sid')

    if not all_addresses:
        return (True, )

    # Insert all senders into `amavisd.mailaddr`
    create_mailaddr(conn=conn, addresses=all_addresses)

    # Get `mailaddr.id` of senders
    sender_records = {}
    if sender_addresses:
        qr = conn.select('mailaddr',
                         vars={'addresses': list(sender_addresses)},
                         what='id, email',
                         where='email IN $addresses')
        for r in qr:
            sender_records[str(r.email)] = r.id
        del qr

    # Get `mailaddr.id` of recipients
    rcpt_records = {}
    if rcpt_addresses:
        qr = conn.select('mailaddr',
                         vars={'addresses': list(rcpt_addresses)},
                         what='id, email',
                         where='email IN $addresses')
        for r in qr:
            rcpt_records[str(r.email)] = r.id
        del qr

    # Remove existing records of current submitted records then insert new.
    try:
        if sender_records:
            conn.delete('wblist',
                        vars={'rid': user_id, 'sid': sender_records.values()},
                        where='rid=$rid AND sid IN $sid')

            if rcpt_records:
                conn.delete('outbound_wblist',
                            vars={'sid': user_id, 'rid': rcpt_records.values()},
                            where='sid=$sid AND rid IN $rid')
    except Exception, e:
        return (False, str(e))

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
            conn.multiple_insert('wblist', values)

        if rcpt_values:
            conn.multiple_insert('outbound_wblist', rcpt_values)

    except Exception, e:
        return (False, str(e))

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
        user_id = qr[1].id
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
            qr = conn.select('mailaddr',
                             vars={'addresses': wl_senders},
                             what='id, email',
                             where='email IN $addresses')
            for r in qr:
                sids.append(r.id)
                wl_smails.append(r.email)

            if sids:
                conn.delete('wblist',
                            vars={'user_id': user_id, 'sids': sids},
                            where="rid=$user_id AND sid IN $sids AND wb='W'")

        if bl_senders:
            sids = []
            bl_smails = []
            qr = conn.select('mailaddr',
                             vars={'addresses': bl_senders},
                             what='id, email',
                             where='email IN $addresses')
            for r in qr:
                sids.append(r.id)
                bl_smails.append(r.email)

            if sids:
                conn.delete('wblist',
                            vars={'user_id': user_id, 'sids': sids},
                            where="rid=$user_id AND sid IN $sids AND wb='B'")

        if wl_rcpts:
            rids = []
            wl_rmails = []
            qr = conn.select('mailaddr',
                             vars={'addresses': wl_rcpts},
                             what='id, email',
                             where='email IN $addresses')
            for r in qr:
                rids.append(r.id)
                wl_rmails.append(r.email)

            if rids:
                conn.delete('outbound_wblist',
                            vars={'user_id': user_id, 'rids': rids},
                            where="sid=$user_id AND rid IN $rids AND wb='W'")

        if bl_rcpts:
            rids = []
            bl_rmails = []
            qr = conn.select('mailaddr',
                             vars={'addresses': bl_rcpts},
                             what='id, email',
                             where='email IN $addresses')
            for r in qr:
                rids.append(r.id)
                bl_rmails.append(r.email)

            if rids:
                conn.delete('outbound_wblist',
                            vars={'user_id': user_id, 'rids': rids},
                            where="sid=$user_id AND rid IN $rids AND wb='B'")

    except Exception, e:
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
        user_id = qr[1].id
    else:
        return qr

    # Remove ALL wblist.
    # No need to remove unused senders in `mailaddr` table, because we
    # have daily cron job to delete them (tools/cleanup_amavisd_db.py).
    try:
        if wl_senders:
            conn.delete('wblist',
                        vars={'user_id': user_id},
                        where="rid=$user_id AND wb='W'")

        if bl_senders:
            conn.delete('wblist',
                        vars={'user_id': user_id},
                        where="rid=$user_id AND wb='B'")

        if wl_rcpts:
            conn.delete('outbound_wblist',
                        vars={'user_id': user_id},
                        where="sid=$user_id AND wb='W'")

        if bl_rcpts:
            conn.delete('outbound_wblist',
                        vars={'user_id': user_id},
                                  where="sid=$user_id AND wb='B'")

    except Exception, e:
        return (False, str(e))

    return (True, )


def get_account_wblist(conn,
                       account,
                       whitelist=True,
                       blacklist=True,
                       outbound_whitelist=True,
                       outbound_blacklist=True):
    """Get white/blacklists of specified account."""
    inbound_sql_where = 'users.email=$user AND users.id=wblist.rid AND wblist.sid = mailaddr.id'
    if whitelist and not blacklist:
        inbound_sql_where += ' AND wblist.wb=%s' % sqlquote('W')
    if not whitelist and blacklist:
        inbound_sql_where += ' AND wblist.wb=%s' % sqlquote('B')

    outbound_sql_where = 'users.email=$user AND users.id=outbound_wblist.sid AND outbound_wblist.rid = mailaddr.id'
    if outbound_whitelist and not outbound_blacklist:
        outbound_sql_where += ' AND outbound_wblist.wb=%s' % sqlquote('W')
    if not whitelist and blacklist:
        outbound_sql_where += ' AND outbound_wblist.wb=%s' % sqlquote('B')

    wl = []
    bl = []
    outbound_wl = []
    outbound_bl = []

    try:
        qr = conn.select(['mailaddr', 'users', 'wblist'],
                         vars={'user': account},
                         what='mailaddr.email AS address, wblist.wb AS wb',
                         where=inbound_sql_where)
        for r in qr:
            if r.wb == 'W':
                wl.append(r.address)
            else:
                bl.append(r.address)

        qr = conn.select(['mailaddr', 'users', 'outbound_wblist'],
                         vars={'user': account},
                         what='mailaddr.email AS address, outbound_wblist.wb AS wb',
                         where=outbound_sql_where)
        for r in qr:
            if r.wb == 'W':
                outbound_wl.append(r.address)
            else:
                outbound_bl.append(r.address)
    except Exception, e:
        return (False, e)

    return (True, {'whitelist': wl,
                   'blacklist': bl,
                   'outbound_whitelist': outbound_wl,
                   'outbound_blacklist': outbound_bl})


