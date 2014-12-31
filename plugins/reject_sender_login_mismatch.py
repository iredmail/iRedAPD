# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Reject sender login mismatch (addresses in 'From:' and SASL username).
#
# How to use this plugin:
#
# *) You must remove "sender_login_mismatch" restriction rule in Postfix
#    setting "smtpd_sender_restrictions" (/etc/postfix/main.cf). this plugin
#    will do the same restriction for you.
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#       plugins = ['reject_sender_login_mismatch', ...]
#
# *) List senders who are allowed to send email as different users in iRedAPD
#    config file (/opt/iredapd/settings.py), in parameter
#    ALLOWED_LOGIN_MISMATCH_SENDERS. For example:
#
#       ALLOWED_LOGIN_MISMATCH_SENDERS = ['domain.com', 'user2@here.com']
#
# *) Set whether or not strictly allow sender to send as one of user alias
#    addresses. Default is True.
#
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = True
#
#    or
#
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = False
#
#    - With OpenLDAP backend, user alias address is stored in attribute
#      'shadowAddress' of user object.
#
#    - With MySQL/PostgreSQL backends, user alias address is username part +
#      alias domain name. For example, if primary domain 'primary.com' has
#      two alias domains: 'alias-1.com', 'alias-2.com'. User 'user@primary.com'
#      is allowed to send email as:
#
#       + user@primary.com
#       + user@alias-1.com
#       + user@alias-2.com.
#
# *) Restart iRedAPD service.

import logging
from libs import SMTP_ACTIONS
import settings

try:
    STRICT_RESTRICTION = settings.ALLOWED_LOGIN_MISMATCH_STRICTLY
except:
    STRICT_RESTRICTION = True

if STRICT_RESTRICTION:
    if settings.backend == 'ldap':
        from libs.ldaplib import conn_utils

reject = 'REJECT Sender login mismatch'


def restriction(**kwargs):
    # Allowed senders or sender domains.
    try:
        ALLOWED_LOGIN_MISMATCH_SENDERS = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
    except:
        logging.debug('SKIP: No allowed senders specified (ALLOWED_LOGIN_MISMATCH_SENDERS).')
        return SMTP_ACTIONS['default']

    sasl_username = kwargs['sasl_username']
    if not sasl_username:
        logging.debug('SKIP: No SASL username.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    sasl_sender_domain = sasl_username.split('@', 1)[-1]

    logging.debug('Sender: %s, SASL username: %s' % (sender, sasl_username))
    logging.debug('Allowed SASL senders: %s' % ', '.join(ALLOWED_LOGIN_MISMATCH_SENDERS))

    # Apply on outgoing emails
    if sender != sasl_username:
        header_sender_domain = sender.split('@', 1)[-1]

        # Check alias domains and user alias addresses
        if STRICT_RESTRICTION:
            logging.debug('Apply strict restriction (ALLOWED_LOGIN_MISMATCH_STRICTLY = True).')

            conn = kwargs['conn']

            if settings.backend == 'ldap':
                if sasl_username in ALLOWED_LOGIN_MISMATCH_SENDERS \
                   or sasl_sender_domain in ALLOWED_LOGIN_MISMATCH_SENDERS:
                    query_filter = '(&(objectClass=mailUser)(mail=%s)(shadowAddress=%s))' % (sasl_username, sender)

                    qr = conn_utils.get_account_ldif(
                        conn=conn,
                        account=sasl_username,
                        query_filter=query_filter,
                        attrs=['dn'],
                    )
                    (dn, entry) = qr
                    if dn:
                        logging.debug('Sender is an user alias address.')
                    else:
                        logging.debug('Sender is not an user alias address.')
                        return reject

            elif settings.backend in ['mysql', 'pgsql']:
                if sasl_username in ALLOWED_LOGIN_MISMATCH_SENDERS \
                   or sasl_sender_domain in ALLOWED_LOGIN_MISMATCH_SENDERS:
                    if header_sender_domain == sasl_sender_domain:
                        # not allowed to send as another user under same domain
                        # in strict restriction mode.
                        return reject

                    # Get alias domains
                    sql = """SELECT alias_domain FROM alias_domain
                             WHERE alias_domain='%s' AND target_domain='%s'
                             LIMIT 1""" % (header_sender_domain, sasl_sender_domain)
                    logging.debug('SQL: query alias domains: %s' % sql)

                    conn.execute(sql)
                    sql_record = conn.fetchone()
                    logging.debug('SQL query result: %s' % str(sql_record))

                    if not sql_record:
                        logging.debug('No alias domain found.')
                        return reject
                    else:
                        logging.debug('Sender domain %s is alias domain of %s.' % (header_sender_domain, sasl_sender_domain))
                        # header_sender_domain is one of alias domains
                        if sender.split('@', 1)[0] != sasl_username.split('@', 1)[0]:
                            logging.debug('Sender is not an user alias address.')
                            return reject
                        else:
                            logging.debug('Sender is an alias address of sasl username.')

        else:
            logging.debug('Not strict restriction (ALLOWED_LOGIN_MISMATCH_STRICTLY = False).')
            if sasl_username in ALLOWED_LOGIN_MISMATCH_SENDERS \
               or sasl_sender_domain in ALLOWED_LOGIN_MISMATCH_SENDERS:
                return SMTP_ACTIONS['default']
            else:
                # Reject with reason.
                return reject

    return SMTP_ACTIONS['default']
