# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Whitelisting and blacklisting a sender server based on reverse DNS
#          (rDNS) name of its IP address.

# Valid rDNS formats:
#
#   - 'domain.co.uk'
#
#       matches exactly reverse DNS name 'domain.co.uk'
#
#   - '.domain.co.uk'
#
#       matches 'domain.co.uk' and all reverse DNS names which end with
#       '.domain.co.uk'. for example:
#
#                 domain.co.uk
#            mail.domain.co.uk
#       smtp.mail.domain.co.uk
#
# --------------
# Sample usages
#
# *) Block rDNS name 'mail.domain.co.uk':
#
#   sql> INSERT INTO wblist_rdns (rdns, wb) VALUES ('mail.domain.co.uk', 'B');
#
# *) Block rDNS name 'dynamic.163.com.cn' and all names which end with it:
#
#   sql> INSERT INTO wblist_rdns (rdns, wb) VALUES ('.dynamic.163data.com.cn', 'B')
#
# *) Whitelist rDNS name 'mx.example.com':
#
#   sql> INSERT INTO wblist_rdns (rdns, wb) VALUES ('mx.example.com', 'W');
#
# *) Whitelist rDNS name 'example.com' and all names which end with it:
#
#   sql> INSERT INTO wblist_rdns (rdns, wb) VALUES ('.example.com', 'W');

from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS
from libs.utils import is_trusted_client
import settings

if settings.WBLIST_DISCARD_INSTEAD_OF_REJECT:
    reject_action = SMTP_ACTIONS['discard']
else:
    reject_action = SMTP_ACTIONS['reject_blacklisted']


def restriction(**kwargs):
    rdns_name = kwargs['smtp_session_data']['reverse_client_name']
    client_address = kwargs['smtp_session_data']['client_address']

    # Bypass outgoing emails.
    if kwargs['sasl_username']:
        logger.debug('Found SASL username, bypass rDNS check for outbound.')
        return SMTP_ACTIONS['default']

    if rdns_name == 'unknown':
        logger.debug('No reverse dns name, bypass.')
        return SMTP_ACTIONS['default']

    if is_trusted_client(client_address):
        return SMTP_ACTIONS['default']

    _policy_rdns_names = [rdns_name]

    _splited = rdns_name.split('.')
    for i in range(len(_splited)):
        _name = '.' + '.'.join(_splited)
        _policy_rdns_names.append(_name)
        _splited.pop(0)

    logger.debug('All policy rDNS names: %s' % repr(_policy_rdns_names))

    conn = kwargs['conn_iredapd']

    # Query whitelist
    sql = """SELECT rdns
               FROM wblist_rdns
              WHERE rdns IN %s AND wb='W'
              LIMIT 1""" % sqlquote(_policy_rdns_names)
    logger.debug('[SQL] Query whitelisted rDNS names: \n%s' % sql)
    qr = conn.execute(sql)
    record = qr.fetchone()
    if record:
        rdns = str(record[0]).lower()
        logger.info(f'[{client_address}] Reverse client hostname is whitelisted: {rdns}.')

        # better use 'DUNNO' instead of 'OK'
        return SMTP_ACTIONS['default']

    # Query blacklist
    sql = """SELECT rdns
               FROM wblist_rdns
              WHERE rdns IN %s AND wb='B'
              LIMIT 1""" % sqlquote(_policy_rdns_names)
    logger.debug('[SQL] Query blacklisted rDNS names: \n%s' % sql)
    qr = conn.execute(sql)
    record = qr.fetchone()
    if record:
        rdns = str(record[0]).lower()
        logger.info(f'[{client_address}] Reverse client hostname is blacklisted: {rdns}')
        return reject_action

    return SMTP_ACTIONS['default']
