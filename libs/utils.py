import re
import logging
import time
from web import sqlquote
from sqlalchemy import create_engine
from libs import SMTP_ACTIONS
from libs import ipaddress
import settings

# Mail address. +, = is used in SRS rewritten addresses.
regx_email = r'''[\w\-][\w\-\.\+\=]*@[\w\-][\w\-\.]*\.[a-zA-Z]{2,15}'''

# Domain name
regx_domain = r'''[\w\-][\w\-\.]*\.[a-z]{2,15}'''

# IP address
regx_ipv4 = r'(?:[\d]{1,3})\.(?:[\d]{1,3})\.(?:[\d]{1,3})\.(?:[\d]{1,3})$'
regx_ipv6 = r'^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$'

# Wildcard sender address: 'user@*'
regx_wildcard_addr = r'''[\w\-][\w\-\.\+\=]*@\*'''

# Convert all IP address, wildcard IPs, subnet to `ipaddress` format.
TRUSTED_IPS = []
TRUSTED_NETWORKS = []
for ip in settings.MYNETWORKS:
    if '/' in ip:
        try:
            TRUSTED_NETWORKS.append(ipaddress.ip_network(unicode(ip)))
        except:
            pass
    else:
        try:
            TRUSTED_IPS.append(ip)
        except:
            pass


def apply_plugin(plugin, **kwargs):
    action = SMTP_ACTIONS['default']

    logging.debug('--> Apply plugin: %s' % plugin.__name__)
    try:
        action = plugin.restriction(**kwargs)
        logging.debug('<-- Result: %s' % action)
    except Exception, e:
        logging.error('<!> Error while applying plugin "%s": %s' % (plugin.__name__, str(e)))

    return action


def is_email(s):
    try:
        s = str(s).strip()
    except UnicodeEncodeError:
        return False

    # Not contain invalid characters and match regular expression
    if not set(s) & set(r'~!#$%^&*()\/ ') \
       and re.compile(regx_email + '$', re.IGNORECASE).match(s):
        return True

    return False


# Valid IP address
def is_ipv4(s):
    if re.match(regx_ipv4, s):
        return True

    return False


def is_ipv6(s):
    if re.match(regx_ipv6, s):
        return True
    return False


def is_strict_ip(s):
    if is_ipv4(s):
        return True
    elif is_ipv6(s):
        return True

    return False


def is_domain(s):
    s = str(s)
    if len(set(s) & set('~!#$%^&*()+\\/\ ')) > 0 or '.' not in s:
        return False

    comp_domain = re.compile(regx_domain + '$', re.IGNORECASE)
    if comp_domain.match(s):
        return True
    else:
        return False


def is_wildcard_addr(s):
    if re.match(regx_wildcard_addr, s):
        return True

    return False


def sqllist(values):
    """
        >>> sqllist([1, 2, 3])
        <sql: '(1, 2, 3)'>
    """
    items = []
    items.append('(')
    for i, v in enumerate(values):
        if i != 0:
            items.append(', ')

        if isinstance(v, (int, long, float)):
            items.append("""%s""" % v)
        else:
            items.append("""'%s'""" % v)
    items.append(')')
    return ''.join(items)


def get_db_conn(db):
    if settings.backend == 'pgsql':
        dbn = 'postgres'
    else:
        dbn = 'mysql'

    try:
        uri = '%s://%s:%s@%s:%d/%s' % (dbn,
                                       settings.__dict__[db + '_db_user'],
                                       settings.__dict__[db + '_db_password'],
                                       settings.__dict__[db + '_db_server'],
                                       int(settings.__dict__[db + '_db_port']),
                                       settings.__dict__[db + '_db_name'])

        conn = create_engine(uri,
                             pool_size=20,
                             pool_recycle=3600,
                             max_overflow=0)
        return conn
    except:
        return None


def wildcard_ipv4(ip):
    ips = []
    if is_ipv4(ip):
        ip4 = ip.split('.')

        if settings.ENABLE_ALL_WILDCARD_IP:
            ip4s = set()
            counter = 0
            for i in range(4):
                a = ip4[:]
                a[i] = '*'
                ip4s.add('.'.join(a))

                if counter < 4:
                    for j in range(4 - counter):
                        a[j+counter] = '*'
                        ip4s.add('.'.join(a))

                counter += 1
            ips += list(ip4s)
        else:
            # 11.22.33.*
            ips.append('.'.join(ip4[:3]) + '.*')
            # 11.22.*.44
            ips.append('.'.join(ip4[:2]) + '.*.' + ip4[3])

    return ips


def is_trusted_client(client_address):
    if client_address in ['127.0.0.1', '::1']:
        logging.debug('Local sender.')
        return True

    if client_address in TRUSTED_IPS:
        logging.debug('Client address (%s) is trusted networks (MYNETWORKS).' % client_address)
        return True

    if set(wildcard_ipv4(client_address)) & set(TRUSTED_IPS):
        logging.debug('Client address (%s) is trusted networks (MYNETWORKS).' % client_address)
        return True

    ip_addr = ipaddress.ip_address(unicode(client_address))
    for net in TRUSTED_NETWORKS:
        if ip_addr in net:
            return True

    return False


def log_action(conn, action, sender, recipient, ip, plugin_name):
    # Don't log certain actions:
    #
    #   - DUNNO
    #   - OK (whitelist)
    #   - 451 ... (greylisting)
    if action.startswith('DUNNO') \
       or action.startswith('OK') \
       or action.startswith('451'):
        return None

    try:
        do_log = settings.log_action_in_db
    except:
        do_log = False

    if not (do_log and conn):
        return None

    # Log action
    try:
        comment = '%s (%s -> %s, %s)' % (action, sender, recipient, plugin_name)
        sql = """INSERT INTO log (admin, ip, msg, timestamp, event)
                          VALUES ('iredapd', '%s', '%s', NOW(), 'iredapd')
        """ % (ip, comment)

        logging.debug(sql)
        conn.execute(sql)
    except Exception, e:
        logging.error(e)


def log_smtp_session(conn, smtp_session_data):
    record = {'time': int(time.time())}
    sql_columns = ['queue_id', 'helo_name',
                   'client_address', 'client_name', 'reverse_client_name',
                   'sender', 'recipient', 'recipient_count',
                   'instance', 'sasl_username', 'size',
                   'encryption_protocol', 'encryption_cipher']

    for col in sql_columns:
        record[col] = sqlquote(smtp_session_data.get(col, ''))

    # TODO query sql db before inserting, make sure no record with same
    #      `instance` value.

    if smtp_session_data['protocol_state'] == 'RCPT':
        # Create new record for new session (protocol_state == RCPT).
        sql_new = """
            INSERT INTO session_tracking (
                        time,
                        helo_name,
                        sender,
                        recipient,
                        client_address,
                        client_name,
                        reverse_client_name,
                        instance,
                        sasl_username,
                        encryption_protocol,
                        encryption_cipher
                        )
                 VALUES (%(time)d,
                         %(helo_name)s,
                         %(sender)s,
                         %(recipient)s,
                         %(client_address)s,
                         %(client_name)s,
                         %(reverse_client_name)s,
                         %(instance)s,
                         %(sasl_username)s,
                         %(encryption_protocol)s,
                         %(encryption_cipher)s)
        """ % record

        try:
            logging.debug('[SQL] Log smtp session: ' + sql_new)
            conn.execute(sql_new)
            logging.debug('Logged smtp session.')
        except Exception, e:
            logging.debug('Logging failed: %s' % str(e))

    elif smtp_session_data['protocol_state'] == 'END-OF-MESSAGE':
        # Update attributes has non-empty value in END-OF-MESSAGE
        sql_update = """
            UPDATE session_tracking
               SET queue_id=%(queue_id)s,
                   size=%(size)s,
                   recipient_count=%(recipient_count)s
             WHERE instance=%(instance)s
        """ % record

        try:
            logging.debug('[SQL] Update smtp session: ' + sql_update)
            conn.execute(sql_update)
        except Exception, e:
            logging.debug('Update failed: %s' % str(e))

    return True


