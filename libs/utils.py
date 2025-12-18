import os
import sys
import traceback
import re
import time
import socket
import subprocess
import smtplib
import ipaddress
import uuid
from dns import resolver # type: ignore
from typing import Union, List, Tuple, Set, Dict, Any

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formatdate

from web import sqlquote
import sqlalchemy
from sqlalchemy import create_engine

# Default SQLAlchemy version: 1.4.x.
__sqlalchemy_version = 1

if sqlalchemy.__version__.startswith('2.'):
    # SQLAlchemy version: 2.x.
    from sqlalchemy import text
    __sqlalchemy_version = 2


from libs.logger import logger
from libs import PLUGIN_PRIORITIES, ACCOUNT_PRIORITIES
from libs import SMTP_ACTIONS
from libs import regxes
import settings

if settings.backend == 'ldap':
    import ldap


# Priority used in SQL table `amavisd.mailaddr` and iRedAPD plugin `throttle`.
# 0 is the lowest priority.
# Reference: http://www.amavis.org/README.lookups.txt
#
# The following order (implemented by sorting on the 'priority' field
# in DESCending order, zero is low priority) is recommended, to follow
# the same specific-to-general principle as in other lookup tables;
#   9 - lookup for user+foo@sub.example.com
#   8 - lookup for user@sub.example.com (only if $recipient_delimiter is '+')
#   7 - lookup for user+foo (only if domain part is local)
#   6 - lookup for user     (only local; only if $recipient_delimiter is '+')
#   5 - lookup for @sub.example.com
#   3 - lookup for @.sub.example.com
#   2 - lookup for @.example.com
#   1 - lookup for @.com
#   0 - lookup for @.       (catchall)
MAILADDR_PRIORITIES = {
    'email': 10,
    'ip': 9,
    'wildcard_ip': 8,
    'cidr_network': 7,      # '192.168.1.0/24'. used in iRedAPD plugin
                            # `amavisd_wblist`
    'wildcard_addr': 7,     # r'user@*'. used in iRedAPD plugin `amavisd_wblist`
                            # as wildcard sender. e.g. 'user@*'
    'domain': 5,
    'subdomain': 3,
    'top_level_domain': 2,
    'catchall_ip': 1,       # used in iRedAPD plugin `throttle`
    'catchall': 0,
}

# Convert all IP address, wildcard IPs, subnet to `ipaddress` format.
TRUSTED_IPS = []
TRUSTED_NETWORKS = []
for ip in settings.MYNETWORKS:
    if '/' in ip:
        try:
            TRUSTED_NETWORKS.append(ipaddress.ip_network(ip))
        except:
            pass
    else:
        try:
            TRUSTED_IPS.append(ip)
        except:
            pass


def get_traceback():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    err_msg = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
    return err_msg


def apply_plugin(plugin, **kwargs):
    action = SMTP_ACTIONS['default']
    plugin_name = plugin.__name__

    logger.debug("--> Apply plugin: {}".format(plugin_name))
    try:
        action = plugin.restriction(**kwargs)
        logger.debug("<-- Result: {}".format(action))
    except:
        err_msg = get_traceback()
        logger.error("<!> Error while applying plugin '{}': {}".format(plugin_name, err_msg))

    return action


def is_email(s):
    try:
        s = str(s).strip()
    except UnicodeEncodeError:
        return False

    # Not contain invalid characters and match regular expression
    if not set(s) & set(r'~!$%^*() ') and regxes.cmp_email.match(s):
        return True

    return False


def is_tld_domain(s):
    s = str(s)

    if regxes.cmp_top_level_domain.match(s):
        return True
    else:
        return False


# Valid IP address
def is_ipv4(s):
    if re.match(regxes.regx_ipv4, s):
        return True

    return False


def is_ipv6(s):
    if re.match(regxes.regx_ipv6, s):
        return True
    return False


def is_strict_ip(s):
    try:
        ipaddress.ip_address(s)
        return True
    except:
        return False


def is_cidr_network(s):
    try:
        ipaddress.ip_network(s)
        return True
    except:
        return False


def is_wildcard_ipv4(s):
    if re.match(regxes.regx_wildcard_ipv4, s):
        return True

    return False


def is_domain(s):
    s = str(s)
    if len(set(s) & set('~!#$%^&*()+\\/ ')) > 0 or '.' not in s:
        return False

    if regxes.cmp_domain.match(s):
        return True
    else:
        return False


def is_wildcard_addr(s):
    if re.match(regxes.regx_wildcard_addr, s):
        return True

    return False


def get_policy_addresses_from_email(mail):
    """Return list of valid policy addresses from given email address.

    >>> get_policy_addresses_from_email(mail="user@sub3.sub2.sub1.com")
    ["user@sub3.sub2.sub1.com",     # full email address
         "@sub3.sub2.sub1.com",     # entire domain (without sub-domains)
        "@.sub3.sub2.sub1.com",     # entire domain with sub-domains
             "@.sub2.sub1.com",     # all sub-sub domains
                  "@.sub1.com",     # all sub-sub-sub domains
                       "@.com",     # all top-level domains
                          "@.",     # catch-all
    ]
    """
    if not is_email(mail):
        return ['@.']

    (_user, _domain) = mail.split('@', 1)
    _domain_parts = _domain.split('.')

    addresses = [mail, '@' + _domain, '@.']
    for (_index, _sub) in enumerate(_domain_parts):
        _addr = '@.' + '.'.join(_domain_parts[_index:])
        addresses.append(_addr)

    return addresses


def is_valid_amavisd_address(addr):
    # Valid address format:
    #
    #   - email: single address. e.g. user@domain.ltd
    #   - domain: @domain.ltd
    #   - subdomain: entire domain and all sub-domains. e.g. @.domain.ltd
    #   - tld_domain: top level domain name. e.g. @.com, @.org.
    #   - catchall: catch all address. @.
    #   - ip: IPv4 or IPv6 address. Used in iRedAPD plugin `amavisd_wblist`
    #   - wildcard_addr: address with wildcard. e.g. 'user@*'. used in wblist.
    #   - wildcard_ip: wildcard IP addresses. e.g. 192.168.1.*.
    #
    # WARNING: don't forget to update MAILADDR_PRIORITIES in
    # libs/amavisd/__init__.py for newly added address format.
    if addr.startswith(r'@.'):
        if addr == r'@.':
            return 'catchall'
        else:
            domain = addr.split(r'@.', 1)[-1]

            if is_domain(domain):
                return 'subdomain'
            elif is_tld_domain(domain):
                return 'top_level_domain'

    elif addr.startswith(r'@'):
        # entire domain
        if addr == '@ip':
            return 'catchall_ip'
        else:
            domain = addr.split(r'@', 1)[-1]
            if is_domain(domain):
                return 'domain'

    elif is_email(addr):
        # single email address
        return 'email'

    elif is_wildcard_addr(addr):
        return 'wildcard_addr'

    elif is_strict_ip(addr):
        return 'ip'
    elif is_cidr_network(addr):
        return 'cidr_network'
    elif is_wildcard_ipv4(addr):
        return 'wildcard_ip'

    return False


def create_db_engine(db_name):
    """Return SQL connection instance with connection pool support."""
    if settings.backend == 'pgsql':
        dbn = 'postgresql'
    else:
        dbn = 'mysql'

    if settings.SQL_DB_DRIVER:
        dbn += '+' + settings.SQL_DB_DRIVER

    _user = settings.__dict__[db_name + '_db_user']
    _pw = settings.__dict__[db_name + '_db_password']
    _server = settings.__dict__[db_name + '_db_server']
    _port = settings.__dict__[db_name + '_db_port']
    _name = settings.__dict__[db_name + '_db_name']
    # New in v6.0, supports SSL connection.
    _use_ssl = settings.__dict__.get(db_name + '_db_use_ssl', False)

    try:
        _port = int(_port)
    except:
        if dbn == 'postgresql':
            _port = 5432
        else:
            _port = 3306

    if not all([_user, _pw, _server, _port, _name]):
        return None

    try:
        uri = '%s://%s:%s@%s:%d/%s' % (dbn, _user, _pw, _server, _port, _name)

        if settings.backend == 'mysql':
            uri += '?charset=utf8'

            if _use_ssl:
                uri += '&ssl_verify_cert=False'

        return create_engine(uri,
                             pool_size=settings.SQL_CONNECTION_POOL_SIZE,
                             pool_recycle=settings.SQL_CONNECTION_POOL_RECYCLE,
                             max_overflow=settings.SQL_CONNECTION_MAX_OVERFLOW)
    except Exception as e:
        logger.error(f"Error while creating SQL connection: {repr(e)}")
        return None


def execute_sql(engine, sql, params=None):
    """Execute SQL query with given db engine, supports both SQLAlchemy 1.4.x and 2.0.x."""
    if __sqlalchemy_version == 2:
        sql = text(sql)

    with engine.connect() as conn:
        with conn.begin():
            return conn.execute(sql, params or {})


def wildcard_ipv4(s):
    ips = []
    if is_ipv4(s):
        ip4 = s.split('.')

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


def is_ip(s):
    """Verify if given string is valid IP (v4, v6) address or network."""
    try:
        # Verify whether it's valid IP address or network.
        if '/' in s:
            if regxes.cmp_ipv4_cidr.match(s) or regxes.cmp_ipv6_cidr.match(s):
                return True
        else:
            if regxes.cmp_ipv4.match(s) or regxes.cmp_ipv6.match(s):
                return True

        return False
    except:
        return False


def is_trusted_client(client_address):
    msg = 'Client address (%s) is trusted (listed in MYNETWORKS).' % client_address

    if client_address in ['127.0.0.1', '::1']:
        logger.debug("Client address is trusted (localhost): {}".format(client_address))
        return True

    if client_address in TRUSTED_IPS:
        logger.debug(msg)
        return True

    if set(wildcard_ipv4(client_address)) & set(TRUSTED_IPS):
        logger.debug(msg)
        return True

    ip_addr = ipaddress.ip_address(client_address)
    for net in TRUSTED_NETWORKS:
        if ip_addr in net:
            logger.debug(msg)
            return True

    return False


def pretty_left_seconds(seconds=0):
    hours = 0
    mins = 0

    # hours
    if seconds >= 3600:
        hours = seconds / 3600
        left_seconds = seconds % 3600
    else:
        left_seconds = seconds

    # minutes
    if left_seconds >= 60:
        mins = left_seconds / 60
        left_seconds = left_seconds % 60

    r = []
    if hours:
        r += ['%d hours' % hours]

    if mins:
        r += ['%d minutes' % mins]

    if left_seconds:
        r += ['%d seconds' % left_seconds]

    if r:
        return 'time left: ' + ', '.join(r)
    else:
        return ''


def get_gmttime():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())


def strip_mail_ext_address(mail, delimiters=None):
    """Remove '+extension' in email address.

    >>> strip_mail_ext_address('user+ext@domain.com')
    'user@domain.com'
    """

    if not is_email(mail):
        return mail

    if not delimiters:
        delimiters = settings.RECIPIENT_DELIMITERS

    (_orig_user, _domain) = mail.split('@', 1)
    for delimiter in delimiters:
        if delimiter in _orig_user:
            (_user, _ext) = _orig_user.split(delimiter, 1)
            return _user + '@' + _domain

    return mail


def get_account_priority(account):
    account_type = is_valid_amavisd_address(account)
    priority = ACCOUNT_PRIORITIES.get(account_type, 0)

    return priority


def is_server_hostname(domain):
    name = socket.gethostname()

    if domain == name:
        return True
    else:
        return False


def log_policy_request(smtp_session_data, action, start_time=None, end_time=None):
    # Log sasl username, sender, recipient
    #   `sender -> recipient`: sender not authenticated
    #   `sender => recipient`: sasl username is same as sender address (From:)
    #   `sasl_username => sender -> recipient`: user send as different sender address
    # @start_time, @end_time are instance of 'time.time()'.
    _log_sender_to_rcpt = ''

    sasl_username = smtp_session_data.get('sasl_username', '')
    sender = smtp_session_data.get('sender', '')
    recipient = smtp_session_data.get('recipient', '')

    client_address = smtp_session_data['client_address']
    protocol_state = smtp_session_data['protocol_state']
    helo = smtp_session_data.get('helo_name', '')
    client_name = smtp_session_data.get('client_name', '')
    reverse_client_name = smtp_session_data.get('reverse_client_name', '').lstrip('[').rstrip(']')

    if sasl_username:
        if sasl_username == sender:
            _log_sender_to_rcpt = f"{sasl_username} => {recipient}"
        else:
            _log_sender_to_rcpt = f"{sasl_username} => {sender} -> {recipient}"
    else:
        _log_sender_to_rcpt = f"{sender} -> {recipient}"

    _time = ''
    if start_time and end_time:
        _shift_time = end_time - start_time
        _time = "{:.4f}s".format(_shift_time)

    # Log final action
    if smtp_session_data['protocol_state'] == 'RCPT':
        logger.info("[{}] {}, {}, "
                    "{} [sasl_username={}, sender={}, "
                    "client_name={}, "
                    "reverse_client_name={}, "
                    "helo={}, "
                    "encryption_protocol={}, "
                    "encryption_cipher={}, "
                    "server_port={}, "
                    "process_time={}]".format(
                        client_address, protocol_state, _log_sender_to_rcpt,
                        action, sasl_username, sender,
                        client_name,
                        reverse_client_name,
                        helo,
                        smtp_session_data.get('encryption_protocol', ''),
                        smtp_session_data.get('encryption_cipher', ''),
                        smtp_session_data.get('server_port', ''),
                        _time))
    else:
        logger.info("[{}] {}, {}, "
                    "{} [recipient_count={}, "
                    "size={}, process_time={}]".format(
                        client_address, protocol_state, _log_sender_to_rcpt,
                        action, smtp_session_data.get('recipient_count', 0),
                        smtp_session_data.get('size', 0), _time))

    return None


def load_enabled_plugins(plugins):
    """Load and import enabled plugins."""
    plugin_dir = os.path.abspath(os.path.dirname(__file__)) + '/../plugins'

    loaded_plugins = []

    # Import priorities of built-in plugins.
    _plugin_priorities = PLUGIN_PRIORITIES

    # Import priorities of custom plugins, or custom priorities of built-in plugins
    _plugin_priorities.update(settings.PLUGIN_PRIORITIES)

    if not plugins:
        plugins = settings.plugins

    # a list of {priority: name}
    pnl = []

    for p in plugins:
        plugin_file = os.path.join(plugin_dir, p + '.py')

        # Skip non-existing plugin.
        if not os.path.isfile(plugin_file):
            logger.error(f"Plugin {p} ({plugin_file}) does not exist.")
            continue

        # If plugin doesn't have a pre-defined priority, set it to 0 (lowest)
        if p not in _plugin_priorities:
            _plugin_priorities[p] = 0

        priority = _plugin_priorities[p]
        pnl += [{'priority': priority, 'plugin': p}]

    # Sort plugin order with pre-defined priorities, so that we can apply
    # plugins in ideal order.
    pnl.sort(key=lambda d: d['priority'], reverse=True)

    ordered_plugins = []
    for item in pnl:
        ordered_plugins.append(item['plugin'])

    for plugin in ordered_plugins:
        try:
            loaded_plugins.append(__import__(plugin))
            logger.info(f"Loading plugin (priority: {_plugin_priorities[plugin]}): {plugin}")
        except Exception as e:
            logger.error(f"Error while loading plugin '{plugin}': {repr(e)}")

    # Get list of LDAP query attributes
    sender_search_attrlist = []
    recipient_search_attrlist = []

    if settings.backend == 'ldap':
        sender_search_attrlist = ['objectClass']
        recipient_search_attrlist = ['objectClass']

        for plugin in loaded_plugins:
            try:
                sender_search_attrlist += plugin.SENDER_SEARCH_ATTRLIST
            except:
                pass

            try:
                recipient_search_attrlist += plugin.RECIPIENT_SEARCH_ATTRLIST
            except:
                pass

    return {'loaded_plugins': loaded_plugins,
            'sender_search_attrlist': sender_search_attrlist,
            'recipient_search_attrlist': recipient_search_attrlist}


def get_required_db_conns():
    """Establish SQL database connections."""
    if settings.backend == 'ldap':
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            conn_vmail = ldap.ldapobject.ReconnectLDAPObject(settings.ldap_uri)
            logger.debug('LDAP connection initialied success.')

            if settings.ldap_enable_tls:
                conn_vmail.start_tls_s()

            # Bind to ldap server.
            try:
                conn_vmail.bind_s(settings.ldap_binddn, settings.ldap_bindpw)
                logger.debug('LDAP bind success.')
            except ldap.INVALID_CREDENTIALS:
                logger.error('LDAP bind failed: incorrect bind dn or password.')
            except Exception as e:
                logger.error(f"LDAP bind failed: {repr(e)}")
        except Exception as e:
            logger.error(f"Failed to establish LDAP connection: {repr(e)}")
            conn_vmail = None
    else:
        # settings.backend in ['mysql', 'pgsql']
        conn_vmail = create_db_engine('vmail')

    engine_amavisd = create_db_engine('amavisd')
    engine_iredapd = create_db_engine('iredapd')

    return {
        'conn_vmail': conn_vmail,
        'engine_amavisd': engine_amavisd,
        'engine_iredapd': engine_iredapd,
    }


def sendmail_with_cmd(from_address, recipients, message_text):
    """Send email with `sendmail` command (defined in CMD_SENDMAIL).

    :param recipients: a list/set/tuple of recipient email addresses, or a
                       string of a single mail address.
    :param message_text: encoded mail message.
    :param from_address: the From: address used while sending email.
    """
    if isinstance(recipients, (list, tuple, set)):
        recipients = ','.join(recipients)

    cmd = [settings.CMD_SENDMAIL, "-f", from_address, recipients]

    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        p.stdin.write(message_text.encode("utf-8"))
        p.stdin.close()
        p.wait()

        return (True, )
    except Exception as e:
        return (False, repr(e))


def sendmail(subject, mail_body, from_address=None, recipients=None):
    """Send email through smtp or with command `sendmail`.

    :param subject: mail subject.
    :param mail_body: plain mail body.
    :param from_address: the address specified in `From:` header.
    :param recipients: a list/set/tuple of recipient email addresses.
    """
    server = settings.NOTIFICATION_SMTP_SERVER
    port = settings.NOTIFICATION_SMTP_PORT
    user = settings.NOTIFICATION_SMTP_USER
    password = settings.NOTIFICATION_SMTP_PASSWORD
    starttls = settings.NOTIFICATION_SMTP_STARTTLS
    debug_level = settings.NOTIFICATION_SMTP_DEBUG_LEVEL

    if not from_address:
        from_address = user

    if not recipients:
        recipients = settings.NOTIFICATION_RECIPIENTS

    #
    # Generate mail message
    #
    msg = MIMEMultipart('alternative')

    _smtp_sender = settings.NOTIFICATION_SMTP_USER
    _smtp_sender_name = settings.NOTIFICATION_SENDER_NAME
    if _smtp_sender_name:
        msg['From'] = '{} <{}>'.format(Header(_smtp_sender_name, 'utf-8'), _smtp_sender)
    else:
        msg['From'] = _smtp_sender

    msg['To'] = ','.join(recipients)
    msg['Subject'] = Header(subject, 'utf-8')
    msg['Date'] = formatdate(usegmt=True)
    msg['Message-Id'] = '<' + str(uuid.uuid4()) + '>'

    msg_body_plain = MIMEText(mail_body, 'plain', 'utf-8')
    msg.attach(msg_body_plain)

    # Get full email as a string.
    message_text = msg.as_string()

    if server and port and user and password:
        # Send email through standard smtp protocol
        try:
            s = smtplib.SMTP(server, port)
            s.set_debuglevel(debug_level)

            if starttls:
                s.ehlo()
                s.starttls()
                s.ehlo()

            s.login(user, password)
            s.sendmail(from_address, recipients, message_text)
            s.quit()
            return (True, )
        except Exception as e:
            return (False, repr(e))
    else:
        return sendmail_with_cmd(from_address=from_address,
                                 recipients=recipients,
                                 message_text=message_text)


def log_smtp_session(engine_iredapd, smtp_action, **smtp_session_data):
    """Store smtp action in SQL table `iredapd.smtp_sessions`."""
    if not settings.LOG_SMTP_SESSIONS:
        return None

    _action_and_reason = smtp_action.split(" ", 1)
    _action = _action_and_reason[0]

    if settings.LOG_SMTP_SESSIONS_BYPASS_GREYLISTING:
        if smtp_action.startswith(SMTP_ACTIONS['greylisting']):
            return None

    if settings.LOG_SMTP_SESSIONS_BYPASS_WHITELIST:
        if _action == 'OK':
            return None

    if len(_action_and_reason) == 1:
        _reason = ''
    else:
        if _action == 'DUNNO':
            _reason = ''
        else:
            _reason = _action_and_reason[1]

    sql = """
        INSERT INTO smtp_sessions (
            time, time_num,
            action, reason, instance,
            client_address, client_name, reverse_client_name, helo_name,
            encryption_protocol, encryption_cipher,
            server_address, server_port,
            sender, sender_domain,
            sasl_username, sasl_domain,
            recipient, recipient_domain)
        VALUES (
            %s, %d,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s)
    """ % (sqlquote(get_gmttime()), int(time.time()),
           sqlquote(_action), sqlquote(_reason),
           sqlquote(smtp_session_data.get("instance", "")),
           sqlquote(smtp_session_data.get("client_address", "")),
           sqlquote(smtp_session_data.get('client_name', '')),
           sqlquote(smtp_session_data.get('reverse_client_name', '')),
           sqlquote(smtp_session_data.get('helo_name', '')),
           sqlquote(smtp_session_data.get('encryption_protocol', '')),
           sqlquote(smtp_session_data.get('encryption_cipher', '')),
           sqlquote(smtp_session_data.get('server_address', '')),
           sqlquote(smtp_session_data.get('server_port', '')),
           sqlquote(smtp_session_data.get('sender_without_ext', '')),
           sqlquote(smtp_session_data.get('sender_domain', '')),
           sqlquote(smtp_session_data.get('sasl_username', '')),
           sqlquote(smtp_session_data.get('sasl_username_domain', '')),
           sqlquote(smtp_session_data.get('recipient_without_ext', '')),
           sqlquote(smtp_session_data.get('recipient_domain', '')))

    try:
        logger.debug(f"[SQL] Insert into smtp_sessions: {sql}")
        execute_sql(engine_iredapd, sql)
    except Exception as e:
        logger.error(f"<!> Error while logging smtp action: {repr(e)}")

    return None


def __bytes2str(b) -> str:
    """Convert object `b` to string.

    >>> __bytes2str("a")
    'a'
    >>> __bytes2str(b"a")
    'a'
    >>> __bytes2str(["a"])  # list: return `repr()`
    "['a']"
    >>> __bytes2str(("a",)) # tuple: return `repr()`
    "('a',)"
    >>> __bytes2str({"a"})  # set: return `repr()`
    "{'a'}"
    """
    if isinstance(b, str):
        return b

    if isinstance(b, (bytes, bytearray)):
        return b.decode()
    elif isinstance(b, memoryview):
        return b.tobytes().decode()
    else:
        return repr(b)


def bytes2str(b: Union[bytes, str, List, Tuple, Set, Dict])\
        -> Union[str, List[str], Tuple[str], Dict[Any, str]]:
    """Convert `b` from bytes-like type to string.

    - If `b` is a string object, returns original `b`.
    - If `b` is a bytes, returns `b.decode()`.

    bytes-like object, return `repr(b)` directly.

    >>> bytes2str("a")
    'a'
    >>> bytes2str(b"a")
    'a'
    >>> bytes2str(["a"])
    ['a']
    >>> bytes2str((b"a",))
    ('a',)
    >>> bytes2str({b"a"})
    {'a'}
    >>> bytes2str({"a": b"a"})      # used to convert LDAP query result.
    {'a': 'a'}
    """
    if isinstance(b, list):
        s = [bytes2str(i) for i in b]
    elif isinstance(b, tuple):
        s = tuple([bytes2str(i) for i in b])
    elif isinstance(b, set):
        s = {bytes2str(i) for i in b}
    elif isinstance(b, dict):
        new_dict = {}
        for (k, v) in list(b.items()):
            new_dict[k] = bytes2str(v)  # v could be list/tuple/dict
        s = new_dict
    else:
        s = __bytes2str(b)

    return s


def get_dns_resolver():
    resv = resolver.Resolver()
    resv.timeout = settings.DNS_QUERY_TIMEOUT
    resv.lifetime = settings.DNS_QUERY_TIMEOUT

    return resv
