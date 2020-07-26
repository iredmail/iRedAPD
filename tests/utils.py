import socket
import web

import settings
from libs.logger import logger
from libs import MAILLIST_POLICY_PUBLIC
from tests import tdata

web.config.debug = False

# We need a sql user which has privilege to insert/update/delete sql records
settings.vmail_db_user = tdata.vmail_db_user
settings.vmail_db_password = tdata.vmail_db_password


def get_db_conn(db_name):
    """Return SQL connection instance with connection pool support."""
    if settings.backend == 'pgsql':
        dbn = 'postgres'
    else:
        dbn = 'mysql'

    try:
        conn = web.database(
            dbn=dbn,
            host=settings.__dict__[db_name + '_db_server'],
            port=int(settings.__dict__[db_name + '_db_port']),
            db=settings.__dict__[db_name + '_db_name'],
            user=settings.__dict__[db_name + '_db_user'],
            pw=settings.__dict__[db_name + '_db_password'],
        )

        return conn
    except Exception as e:
        logger.error('Error while create SQL connection: %s' % repr(e))
        return None


conn = get_db_conn('vmail')
conn_iredapd = get_db_conn('iredapd')


def set_smtp_session(**kw):
    """Generate sample smtp session data.

    Key/value pairs which are not used will be silently ignored.
    """
    d = {
        'request': 'smtpd_access_policy',
        'protocol_state': 'RCPT',
        'protocol_name': 'SMTP',
        'recipient_count': '0',
        'client_address': '192.168.1.1',
        'reverse_client_name': 'another.domain.tld',
        'instance': '123.456.7',
        'size': '123',
        # 'helo_name': 'some.domain.tld',
        # 'queue_id': '8045F2AB23',
        # 'sender': 'postmaster@a.cn',
        # 'recipient': 'test@b.cn',
        # 'client_name': 'another.domain.tld',
        # 'sasl_method': 'plain',
        # 'sasl_username': 'postmaster@a.cn',
        # 'sasl_sender': '',
        # 'ccert_subject': '',
        # 'ccert_issuer': '',
        # 'ccert_fingerprint': '',
        # 'encryption_protocol': '',
        # 'encryption_cipher': '',
        # 'encryption_keysize': '',
        # 'etrn_domain': '',
        # 'stress': '',
        # 'ccert_pubkey_fingerprint': '',
    }

    d.update(**kw)

    items = ['{}={}'.format(k, v) for k, v in list(d.items())]
    return '\n'.join(items) + '\n\n'


def send_policy(d):
    """Send smtp session data to Postfix policy server. Return policy action."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 7777))
    s.sendall(d)
    reply = s.recv(1024)
    s.close()

    reply = reply.strip().lstrip(b'action=')
    return reply


def add_domain(domain=tdata.domain):
    delete_domain()
    conn.insert('domain', domain=domain)


def delete_domain():
    delete_alias_domain()
    conn.delete('domain',
                vars=tdata.sql_vars,
                where='domain=$domain')
    conn.delete('alias',
                vars=tdata.sql_vars,
                where='domain=$domain')
    conn.delete('moderators',
                vars=tdata.sql_vars,
                where='domain=$domain')
    conn.delete('forwardings',
                vars=tdata.sql_vars,
                where='domain=$domain')


def add_alias_domain():
    delete_alias_domain()
    conn.insert('alias_domain',
                alias_domain=tdata.alias_domain,
                target_domain=tdata.domain)


def delete_alias_domain():
    conn.delete('alias_domain',
                vars=tdata.sql_vars,
                where='alias_domain=$alias_domain AND target_domain=$domain')


def add_user(user=tdata.user):
    delete_user()
    conn.insert('mailbox',
                username=tdata.user,
                domain=tdata.domain)

    conn.insert('forwardings',
                address=tdata.user,
                forwarding=tdata.user,
                domain=user.split('@', 1)[-1],
                is_forwarding=1)


def delete_user():
    conn.delete('mailbox',
                vars=tdata.sql_vars,
                where='username=$user')

    # mail forwarding
    conn.delete('forwardings',
                vars=tdata.sql_vars,
                where='address=$user AND is_forwarding=1')

    # per-user alias address
    conn.delete('forwardings',
                vars=tdata.sql_vars,
                where='forwarding=$user AND is_alias=1')

    # iredapd: throttle tracking
    conn_iredapd.delete('throttle_tracking',
                        vars=tdata.sql_vars,
                        where='account=$user')

    # iredapd: greylisting tracking
    conn_iredapd.delete('greylisting_tracking',
                        vars=tdata.sql_vars,
                        where='sender=$ext_user')


def add_per_user_alias_address(user=tdata.user):
    conn.insert('forwardings',
                address=tdata.user_alias,
                forwarding=user,
                domain=user.split('@', 1)[-1],
                is_alias=1)


def add_alias(alias=tdata.user, policy=MAILLIST_POLICY_PUBLIC):
    delete_alias()
    conn.insert('alias',
                address=tdata.alias,
                accesspolicy=policy,
                domain=alias.split('@', 1)[-1])


def delete_alias():
    conn.delete('alias',
                vars=tdata.sql_vars,
                where='address=$alias')

    conn.delete('forwardings',
                vars=tdata.sql_vars,
                where='address=$alias AND is_list=1')


def assign_alias_member(member=tdata.user, alias=tdata.alias):
    conn.insert('forwardings',
                address=alias,
                forwarding=member,
                domain=alias.split('@', 1)[-1],
                is_list=1)


def assign_alias_moderator(moderator=tdata.user, alias=tdata.alias):
    conn.insert('moderators',
                address=alias,
                moderator=moderator,
                domain=alias.split('@', 1)[-1])


def remove_alias_member(member=tdata.user, alias=tdata.alias):
    conn.delete('forwardings',
                vars={'member': member, 'alias': alias},
                where='address=$alias AND forwarding=$member')


def remove_alias_moderator(moderator=tdata.user, alias=tdata.alias):
    conn.delete('moderators',
                vars={'moderator': moderator, 'alias': alias},
                where='address=$alias AND moderator=$moderator')


def add_wblist_rdns_whitelist(rdns):
    remove_wblist_rdns_whitelist(rdns=rdns)
    conn_iredapd.insert('wblist_rdns',
                        rdns=rdns,
                        wb='W')


def remove_wblist_rdns_whitelist(rdns):
    conn_iredapd.delete('wblist_rdns',
                        vars={'rdns': rdns},
                        where="rdns=$rdns AND wb='W'")


def add_wblist_rdns_blacklist(rdns):
    remove_wblist_rdns_blacklist(rdns=rdns)
    conn_iredapd.insert('wblist_rdns',
                        rdns=rdns,
                        wb='B')


def remove_wblist_rdns_blacklist(rdns):
    conn_iredapd.delete('wblist_rdns',
                        vars={'rdns': rdns},
                        where="rdns=$rdns AND wb='B'")
