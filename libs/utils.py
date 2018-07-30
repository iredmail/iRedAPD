import os
import sys
import traceback
import re
import time
import socket

from sqlalchemy import create_engine

from libs.logger import logger
from libs import PLUGIN_PRIORITIES, ACCOUNT_PRIORITIES
from libs import SMTP_ACTIONS, TCP_REPLIES
from libs import regxes
from libs import ipaddress
import settings

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
            TRUSTED_NETWORKS.append(ipaddress.ip_network(unicode(ip)))
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

    logger.debug('--> Apply plugin: %s' % plugin_name)
    try:
        action = plugin.restriction(**kwargs)
        logger.debug('<-- Result: %s' % action)
    except:
        err_msg = get_traceback()
        logger.error('<!> Error while applying plugin "%s": %s' % (plugin_name, err_msg))

    return action


def apply_tcp_table_plugin(plugin, **kwargs):
    action = TCP_REPLIES['default']

    logger.debug('--> Apply tcp table plugin: %s' % plugin.__name__)
    try:
        action = plugin.restriction(**kwargs)
        logger.debug('<-- Result: %s' % action)
    except:
        err_msg = get_traceback()
        logger.error('<!> Error while applying plugin "%s": %s' % (plugin.__name__, err_msg))

    return action


def is_email(s):
    try:
        s = str(s).strip()
    except UnicodeEncodeError:
        return False

    # Not contain invalid characters and match regular expression
    if not set(s) & set(r'~!$%^&*()\/ ') and regxes.cmp_email.match(s):
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
        ipaddress.ip_address(unicode(s))
        return True
    except:
        return False


def is_cidr_network(s):
    try:
        ipaddress.ip_network(unicode(s))
        return True
    except:
        return False

def is_wildcard_ipv4(s):
    if re.match(regxes.regx_wildcard_ipv4, s):
        return True

    return False


def is_domain(s):
    s = str(s)
    if len(set(s) & set('~!#$%^&*()+\\/\ ')) > 0 or '.' not in s:
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
    # Return list valid policy addresses from a given email address
    #
    # - Sample input: mail=user@sub2.sub1.com.cn
    # - Valid policy addresses:
    #   * user@sub2.sub1.com.cn
    #   * @sub2.sub1.com.cn
    #   * @.sub2.sub1.com.cn
    #   * @.sub1.com.cn
    #   * @.com.cn
    #   * @.cn
    #   * @.        # catch-all
    (_username, _domain) = mail.split('@', 1)
    splited_domain_parts = _domain.split('.')

    # Default senders (user@domain.ltd):
    # ['@.', 'user@domain.ltd', @domain.ltd']
    valid_addresses = [mail, '@' + _domain, '@.']

    for counter in range(len(splited_domain_parts)):
        # Append domain and sub-domain.
        subd = '.'.join(splited_domain_parts)
        valid_addresses.append('@.' + subd)
        splited_domain_parts.pop(0)

    return valid_addresses


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


def get_db_conn(db):
    """Return SQL connection instance with connection pool support."""
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

        uri += '?charset=utf8'

        conn = create_engine(uri,
                             pool_size=settings.SQL_CONNECTION_POOL_SIZE,
                             pool_recycle=settings.SQL_CONNECTION_POOL_RECYCLE,
                             max_overflow=settings.SQL_CONNECTION_MAX_OVERFLOW)
        return conn
    except Exception, e:
        logger.error('Error while create SQL connection: %s' % repr(e))
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
    msg = 'Client address (%s) is trusted networks (MYNETWORKS).' % client_address

    if client_address in ['127.0.0.1', '::1']:
        logger.debug('Client address is trusted localhost: %s.' % client_address)
        return True

    if client_address in TRUSTED_IPS:
        logger.debug(msg)
        return True

    if set(wildcard_ipv4(client_address)) & set(TRUSTED_IPS):
        logger.debug(msg)
        return True

    ip_addr = ipaddress.ip_address(unicode(client_address))
    for net in TRUSTED_NETWORKS:
        if ip_addr in net:
            logger.debug(msg)
            return True

    return False


def pretty_left_seconds(seconds=0):
    hours = 0
    mins = 0
    left_seconds = 0

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
    # Convert local time to UTC
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

    protocol_state = smtp_session_data['protocol_state']
    helo = smtp_session_data.get('helo_name', '')
    client_name = smtp_session_data.get('client_name', '')
    reverse_client_name = smtp_session_data.get('reverse_client_name', '').lstrip('[').rstrip(']')

    if sasl_username:
        if sasl_username == sender:
            _log_sender_to_rcpt = '%s => %s' % (sasl_username, recipient)
        else:
            _log_sender_to_rcpt = '%s => %s -> %s' % (sasl_username, sender, recipient)
    else:
        _log_sender_to_rcpt = '%s -> %s' % (sender, recipient)

    _time = ''
    if start_time and end_time:
        _time = '%.4fs' % (end_time - start_time)

    # Log final action
    if smtp_session_data['protocol_state'] == 'RCPT':
        logger.info('[%s] %s, %s, %s [sasl_username=%s, sender=%s, client_name=%s, reverse_client_name=%s, helo=%s, encryption_protocol=%s, process_time=%s]' % (
            smtp_session_data['client_address'],
            protocol_state,
            _log_sender_to_rcpt,
            action,
            sasl_username,
            sender,
            client_name,
            reverse_client_name,
            helo,
            smtp_session_data.get('encryption_protocol', ''),
            _time))
    else:
        logger.info('[%s] %s, %s, %s [recipient_count=%s, size=%s, process_time=%s]' % (
            smtp_session_data['client_address'],
            protocol_state,
            _log_sender_to_rcpt,
            action,
            smtp_session_data.get('recipient_count', '0'),
            smtp_session_data.get('size', '0'),
            _time))

    return None


def load_enabled_plugins(plugins=None):
    """Load and import enabled plugins."""
    plugin_dir = os.path.abspath(os.path.dirname(__file__)) + '/../plugins'

    loaded_plugins = []
    loaded_tcp_table_plugin = None

    # Import priorities of built-in plugins.
    _plugin_priorities = PLUGIN_PRIORITIES

    # Import priorities of custom plugins, or custom priorities of built-in plugins
    _plugin_priorities.update(settings.PLUGIN_PRIORITIES)

    if not plugins:
        plugins = settings.plugins

    if 'custom_tcp_table' in plugins:
        plugins.remove('custom_tcp_table')

        # Load tcp table plugin
        plugin_file = os.path.join(plugin_dir, 'custom_tcp_table.py')
        if not os.path.isfile(plugin_file):
            logger.debug('Plugin custom_tcp_table does not exist, SKIP.')
        else:
            try:
                logger.info('Loading plugin custom_tcp_table')
                loaded_tcp_table_plugin = __import__('custom_tcp_table')
            except Exception, e:
                logger.error('Error while loading plugin custom_tcp_table: %s' % repr(e))

    # If enabled plugin doesn't have a priority pre-defined, set it to 0 (lowest)
    _plugins_without_priority = [i for i in plugins if i not in _plugin_priorities]
    for _p in _plugins_without_priority:
        _plugin_priorities[_p] = 0

    # a list of {priority: name}
    pnl = []
    for p in plugins:
        plugin_file = os.path.join(plugin_dir, p + '.py')
        if not os.path.isfile(plugin_file):
            logger.error('Plugin %s (%s) does not exist.' % (p, plugin_file))
            continue

        priority = _plugin_priorities[p]
        pnl += [{priority: p}]

    # Sort plugin order with pre-defined priorities, so that we can apply
    # plugins in ideal order.
    ordered_plugins = []
    for item in sorted(pnl, reverse=True):
        ordered_plugins += item.values()

    for plugin in ordered_plugins:
        try:
            loaded_plugins.append(__import__(plugin))
            logger.info('Loading plugin (priority: %s): %s' % (_plugin_priorities[plugin], plugin))
        except Exception, e:
            logger.error('Error while loading plugin (%s): %s' % (plugin, repr(e)))

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
            'loaded_tcp_table_plugin': loaded_tcp_table_plugin,
            'sender_search_attrlist': sender_search_attrlist,
            'recipient_search_attrlist': recipient_search_attrlist}


def get_required_db_conns():
    """Establish SQL database connections."""
    if settings.backend in ['mysql', 'pgsql']:
        conn_vmail = get_db_conn('vmail')
    else:
        # we don't have ldap connection pool, a connection object will be
        # created in libs/ldaplib/modeler.py.
        conn_vmail = None

    conn_amavisd = get_db_conn('amavisd')
    conn_iredapd = get_db_conn('iredapd')

    return {'conn_vmail': conn_vmail,
            'conn_amavisd': conn_amavisd,
            'conn_iredapd': conn_iredapd}
