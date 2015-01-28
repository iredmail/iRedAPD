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
# *) Optional setting: List senders who are allowed to send email as different
#    users in iRedAPD config file (/opt/iredapd/settings.py). Sample setting:
#
#       ALLOWED_LOGIN_MISMATCH_SENDERS = ['domain.com', 'user2@here.com']
#
#    If no sender spcified, all users are allowed to send as different users,
#    except you have other optional settings (listed below) enabled.
#
#    Note: this setting doesn't need to be used together with optional settings
#    listed below.
#
# *) Optional setting: Set whether or not strictly allow sender to send as one
#    of user alias addresses. Default is True.
#
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = True
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
#       + user@alias-2.com
#
# *) Optional setting: set whether or not allow member of mail lists/alias
#    account to send email as mail list/alias ('From: <list@domain.ltd>' in
#    mail header. Default is False. Sample setting:
#
#       ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = True
#
# *) Restart iRedAPD service.

import logging
from libs import SMTP_ACTIONS
import settings

# Allowed senders or sender domains.
try:
    ALLOWED_SENDERS = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
except:
    ALLOWED_SENDERS = []

try:
    STRICT_RESTRICTION = settings.ALLOWED_LOGIN_MISMATCH_STRICTLY
except:
    STRICT_RESTRICTION = True

try:
    ALLOW_LIST_MEMBER = settings.ALLOWED_LOGIN_MISMATCH_LIST_MEMBER
except:
    ALLOW_LIST_MEMBER = False

if STRICT_RESTRICTION or ALLOW_LIST_MEMBER:
    if settings.backend == 'ldap':
        from libs.ldaplib import conn_utils

reject = 'REJECT Sender login mismatch'


def restriction(**kwargs):
    if not (ALLOWED_SENDERS or STRICT_RESTRICTION or ALLOW_LIST_MEMBER):
        logging.debug('SKIP: No allowed senders.')
        return SMTP_ACTIONS['default']

    sasl_username = kwargs['sasl_username']
    if not sasl_username:
        logging.debug('SKIP: No SASL username.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    logging.debug('Sender: %s, SASL username: %s' % (sender, sasl_username))

    if sender == sasl_username:
        logging.debug('SKIP: Sender <=> sasl username matched.')
        return SMTP_ACTIONS['default']

    (sasl_sender_name, sasl_sender_domain) = sasl_username.split('@', 1)
    (sender_name, sender_domain) = sender.split('@', 1)

    if ALLOWED_SENDERS:
        logging.debug('Allowed SASL senders: %s' % ', '.join(ALLOWED_SENDERS))
        if not (sasl_username in ALLOWED_SENDERS or sasl_sender_domain in ALLOWED_SENDERS):
            logging.debug('REJECT: Sender is not allowed to send email as other user (ALLOWED_LOGIN_MISMATCH_SENDERS).')
            return reject

    # Check alias domains and user alias addresses
    if STRICT_RESTRICTION or ALLOW_LIST_MEMBER:
        if STRICT_RESTRICTION:
            logging.debug('Apply strict restriction (ALLOWED_LOGIN_MISMATCH_STRICTLY=True).')

        if ALLOW_LIST_MEMBER:
            logging.debug('Apply list/alias member restriction (ALLOWED_LOGIN_MISMATCH_LIST_MEMBER=True).')

        conn = kwargs['conn']

        if settings.backend == 'ldap':
            filter_user_alias = '(&(objectClass=mailUser)(mail=%s)(shadowAddress=%s))' % (sasl_username, sender)
            filter_list_member = '(&(objectClass=mailUser)(|(mail=%s)(shadowAddress=%s))(memberOfGroup=%s))' % (sasl_username, sasl_username, sender)
            filter_alias_member = '(&(objectClass=mailAlias)(|(mail=%s)(shadowAddress=%s))(mailForwardingAddress=%s))' % (sender, sender, sasl_username)

            if STRICT_RESTRICTION and ALLOW_LIST_MEMBER:
                query_filter = '(|' + filter_user_alias + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender (%s) is an user alias address or list/alias member (%s).' % (sasl_username, sender)
            elif STRICT_RESTRICTION and not ALLOW_LIST_MEMBER:
                # Query mail account directly
                query_filter = filter_user_alias
                success_msg = 'Sender is an user alias address.'
            elif not STRICT_RESTRICTION and ALLOW_LIST_MEMBER:
                query_filter = '(|' + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender (%s) is member of mail list/alias (%s).' % (sasl_username, sender)
            else:
                success_msg = 'unknown error'

            qr = conn_utils.get_account_ldif(
                conn=conn,
                account=sasl_username,
                query_filter=query_filter,
                attrs=['dn'],
            )
            (dn, entry) = qr
            if dn:
                logging.debug(success_msg)
                return SMTP_ACTIONS['default']
            else:
                logging.debug('Sender is either an user alias address or list/alias member.')
                return reject

        elif settings.backend in ['mysql', 'pgsql']:
            if STRICT_RESTRICTION:
                # Get alias domains
                sql = """SELECT alias_domain FROM alias_domain
                         WHERE alias_domain='%s' AND target_domain='%s'
                         LIMIT 1""" % (sender_domain, sasl_sender_domain)
                logging.debug('SQL: query alias domains: %s' % sql)

                conn.execute(sql)
                sql_record = conn.fetchone()
                logging.debug('SQL query result: %s' % str(sql_record))

                if not sql_record:
                    logging.debug('No alias domain found.')
                else:
                    logging.debug('Sender domain %s is alias domain of %s.' % (sender_domain, sasl_sender_domain))
                    # sender_domain is one of alias domains
                    if sender_name != sasl_sender_name:
                        logging.debug('Sender is not an user alias address.')
                    else:
                        logging.debug('Sender is an alias address of sasl username.')
                        return SMTP_ACTIONS['default']

            if ALLOW_LIST_MEMBER:
                # Get alias members
                sql = """SELECT goto FROM alias
                         WHERE address='%s'
                         LIMIT 1""" % (sender)
                logging.debug('SQL: query members of alias account: %s' % sql)

                conn.execute(sql)
                sql_record = conn.fetchone()
                logging.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    members = sql_record[0].split(',')
                    if sasl_username in members:
                        logging.debug('Sender (%s) is member of mail alias (%s).' % (sasl_username, sender))
                        return SMTP_ACTIONS['default']
                else:
                    logging.debug('No such mail alias account.')

    return reject
