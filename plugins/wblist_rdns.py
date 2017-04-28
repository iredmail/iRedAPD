# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Blacklisting based on reverse DNS (rDNS) name of client IP address.

# Valid rDNS formats:
#
#   - 'domain.co.uk'
#
#       matches exactly reverse DNS name 'domain.co.uk'
#
#   - '.domain.co.uk'
#
#       matches 'domain.com.uk' and all reverse DNS names which end with
#       '.domain.co.uk'. for example:
#
#                 domain.co.uk
#            mail.domain.co.uk
#       smtp.mail.domain.co.uk
#
#--------------
# Sample usages
#
# *) Block rDNS name 'mail.domain.co.uk':
#
#   sql> INSERT INTO blacklist_rdns (rdns) VALUES ('mail.domain.co.uk');
#
# *) Block all rDNS names which end with '.dynamic.163data.com.cn':
#
#   sql> INSERT INTO blacklist_rdns (rdns) VALUES ('.dynamic.163data.com.cn')

from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS
from libs.utils import is_trusted_client


def restriction(**kwargs):
    rdns_name = kwargs['smtp_session_data']['reverse_client_name']

    # Bypass outgoing emails.
    #if kwargs['sasl_username']:
    #    logger.debug('Found SASL username, bypass rDNS check for outbound.')
    #    return SMTP_ACTIONS['default']

    if rdns_name == 'unknown':
        logger.debug('No reverse dns name, bypass.')
        return SMTP_ACTIONS['default']

    if is_trusted_client(kwargs['client_address']):
        return SMTP_ACTIONS['default']

    _policy_rdns_names = [rdns_name]

    _splited = rdns_name.split('.')
    for i in range(len(_splited)):
        _name = '.' + '.'.join(_splited)
        _policy_rdns_names.append(_name)
        _splited.pop(0)

    logger.debug('All policy rDNS names: %s' % repr(_policy_rdns_names))

    # Query matched rDNS names
    conn = kwargs['conn_iredapd']

    sql = """SELECT rdns FROM blacklist_rdns WHERE rdns IN %s LIMIT 1""" % sqlquote(_policy_rdns_names)
    logger.debug('[SQL] Query matched rDNS names: \n%s' % sql)
    qr = conn.execute(sql)
    record = qr.fetchone()
    if record:
        return SMTP_ACTIONS['reject_blacklisted_rdns']

    return SMTP_ACTIONS['default']
