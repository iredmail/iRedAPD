import re
import logging
import web
from libs import SMTP_ACTIONS
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
    record = {}
    sql_columns = ['queue_id', 'helo_name',
                   'client_address', 'client_name', 'reverse_client_name',
                   'sender', 'recipient', 'recipient_count',
                   'instance', 'sasl_username', 'size',
                   'encryption_protocol', 'encryption_cipher']

    for col in sql_columns:
        record[col] = web.sqlquote(smtp_session_data[col])

    # TODO query sql db before inserting, make sure no record with same
    #      `instance` value.

    # TODO Only insert when `protocol_state=RCPT`.

    # TODO Update queue_id, recipient_count, size when
    #      `protocol_state=END-OF-MESSAGE` with `instance=`

    sql = """
        INSERT INTO session_tracking (
                    queue_id,
                    helo_name,
                    sender,
                    recipient,
                    recipient_count,
                    client_address,
                    client_name,
                    reverse_client_name,
                    instance,
                    -- Postfix version 2.2 and later:
                    -- sasl_method,
                    sasl_username,
                    -- sasl_sender,
                    size,
                    -- ccert_subject,
                    -- ccert_issuer,
                    -- ccert_fingerprint,
                    -- Postfix version 2.3 and later:
                    encryption_protocol,
                    encryption_cipher
                    -- encryption_keysize,
                    -- etrn_domain,
                    -- Postfix version 2.5 and later:
                    -- stress,
                    -- Postfix version 2.9 and later:
                    -- ccert_pubkey_fingerprint,
                    -- Postfix version 3.0 and later:
                    -- client_port
                    )
             VALUES (%(queue_id)s,
                     %(helo_name)s,
                     %(sender)s,
                     %(recipient)s,
                     %(recipient_count)s,
                     %(client_address)s,
                     %(client_name)s,
                     %(reverse_client_name)s,
                     %(instance)s,
                     %(sasl_username)s,
                     %(size)s,
                     %(encryption_protocol)s,
                     %(encryption_cipher)s)
    """ % record

    logging.debug('[SQL] Log smtp session: ' + sql)

    try:
        conn.execute(sql)
        logging.debug('Logged smtp session.')
    except Exception, e:
        logging.debug('Logging failed: %s' % str(e))

    return True
