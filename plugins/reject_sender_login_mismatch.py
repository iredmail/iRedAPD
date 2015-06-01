# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Reject sender login mismatch (addresses in 'From:' and SASL username).
#
# How to use this plugin:
#
# *) You must remove "sender_login_mismatch" restriction rule in Postfix
#    setting "smtpd_sender_restrictions" (/etc/postfix/main.cf). this plugin
#    will do the same and additonal restrictions for you.
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#       plugins = ['reject_sender_login_mismatch', ...]
#
#    Note: please check suggested order of plugins in `settings.py.sample`.
#
# *) Optional settings (set in iRedAPD config file /opt/iredapd/settings.py):
#
#   1) List senders who are allowed to send email as different
#      users in iRedAPD config file (/opt/iredapd/settings.py). Sample setting:
#
#       ALLOWED_LOGIN_MISMATCH_SENDERS = ['domain.com', 'user2@here.com']
#
#      If no sender spcified, no users are allowed to send as different users,
#      except you have other optional settings (listed below) enabled.
#
#      Note: this setting doesn't need to be used together with optional
#      settings listed below.
#
#  2) Set whether or not strictly allow sender to send as one of user alias
#     addresses. Default is True.
#
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = True
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = False
#
#     - With OpenLDAP backend, user alias address is stored in attribute
#       `shadowAddress` of user object.
#
#     - With MySQL/PostgreSQL backends, user alias address is username part +
#       alias domain name. For example, if primary domain `primary.com` has
#       two alias domains: `alias-1.com`, `alias-2.com`. User `user@primary.com`
#       is allowed to send email as:
#
#       + user@primary.com
#       + user@alias-1.com
#       + user@alias-2.com
#
#  3) set whether or not allow member of mail lists/alias account to send email
#     as mail list/alias ('From: <list@domain.ltd>' in mail header). Default is
#     False. Sample setting:
#
#       ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = True
#
# *) Restart iRedAPD service.

import logging
from libs import SMTP_ACTIONS
import settings


allowed_senders = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
is_strict = settings.ALLOWED_LOGIN_MISMATCH_STRICTLY
allow_list_member = settings.ALLOWED_LOGIN_MISMATCH_LIST_MEMBER

if is_strict or allow_list_member:
    if settings.backend == 'ldap':
        from libs.ldaplib import conn_utils

reject = 'REJECT Sender login mismatch'


def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']
    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient_domain = kwargs['recipient_domain']
    client_address = kwargs['smtp_session_data']['client_address']

    conn = kwargs['conn_vmail']

    if not sasl_username:
        logging.debug('Not an authenticated sender (no sasl_username).')

        # Bypass localhost.
        # NOTE: if sender sent email through SOGo, smtp session may not
        #       have sasl_username.
        if client_address in ['127.0.0.1', '::1']:
            logging.debug('Bypass local sender.')
            return SMTP_ACTIONS['default']

        if client_address in settings.MYNETWORKS:
            logging.debug('Bypass sender from trusted/internal networks (%s).' % client_address)
            return SMTP_ACTIONS['default']

        sender_is_forged = False
        if sender_domain == recipient_domain:
            # *) sender == recipient, sender must log in first.
            # *) sender != recipient but under same domain, since domain is
            #    hosted locally, sender must login first too.
            logging.debug('Sender is forged address (sender domain == recipient domain).')
            sender_is_forged = True
        else:
            # Check whether sender domain is hosted on localhost
            if settings.backend == 'ldap':
                filter_domains = '(&(objectClass=mailDomain)'
                filter_domains += '(|(domainName=%s)(domainAliasName=%s))' % (sender_domain, sender_domain)
                filter_domains += ')'

                qr = conn.search_s(settings.ldap_basedn,
                                   1,   # 1 == ldap.SCOPE_ONELEVEL
                                   filter_domains,
                                   ['dn'])
                if qr:
                    logging.debug('Sender is forged address (sender domain is hosted locally).')
                    sender_is_forged = True

            elif settings.backend in ['mysql', 'pgsql']:
                sql = """SELECT alias_domain FROM alias_domain
                         WHERE alias_domain='%s' OR target_domain='%s'
                         LIMIT 1""" % (sender_domain, sender_domain)
                logging.debug('SQL: query alias domains: %s' % sql)

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logging.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    logging.debug('Sender is forged address (sender domain is hosted locally).')
                    sender_is_forged = True

        if sender_is_forged:
            return SMTP_ACTIONS['reject'] + ' not logged in'
        else:
            logging.debug('Sender domain is not hosted locally.')
            return SMTP_ACTIONS['default']

    logging.debug('Sender: %s, SASL username: %s' % (sender, sasl_username))

    if sender == sasl_username:
        logging.debug('SKIP: sender = sasl username.')
        return SMTP_ACTIONS['default']
    else:
        if not (allowed_senders or is_strict or allow_list_member):
            logging.debug('No allowed senders in config file.')
            return reject

    (sasl_sender_name, sasl_sender_domain) = sasl_username.split('@', 1)
    (sender_name, sender_domain) = sender.split('@', 1)

    if allowed_senders:
        logging.debug('Allowed SASL senders: %s' % ', '.join(allowed_senders))
        if sasl_username in allowed_senders or sasl_sender_domain in allowed_senders:
            return SMTP_ACTIONS['default']
        else:
            logging.debug('Sender is not allowed to send email as other user (ALLOWED_LOGIN_MISMATCH_SENDERS).')

    # Check alias domains and user alias addresses
    if is_strict or allow_list_member:
        if is_strict:
            logging.debug('Apply strict restriction (ALLOWED_LOGIN_MISMATCH_STRICTLY=True).')

        if allow_list_member:
            logging.debug('Apply list/alias member restriction (ALLOWED_LOGIN_MISMATCH_LIST_MEMBER=True).')

        if settings.backend == 'ldap':
            filter_user_alias = '(&(objectClass=mailUser)(mail=%s)(shadowAddress=%s))' % (sasl_username, sender)
            filter_list_member = '(&(objectClass=mailUser)(|(mail=%s)(shadowAddress=%s))(memberOfGroup=%s))' % (sasl_username, sasl_username, sender)
            filter_alias_member = '(&(objectClass=mailAlias)(|(mail=%s)(shadowAddress=%s))(mailForwardingAddress=%s))' % (sender, sender, sasl_username)

            if allowed_senders and allow_list_member:
                query_filter = '(|' + filter_user_alias + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender (%s) is an user alias address or list/alias member (%s).' % (sasl_username, sender)
            elif is_strict and not allow_list_member:
                # Query mail account directly
                query_filter = filter_user_alias
                success_msg = 'Sender is an user alias address.'
            elif not is_strict and allow_list_member:
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
            if is_strict:
                # Get alias domains
                sql = """SELECT alias_domain FROM alias_domain
                         WHERE alias_domain='%s' AND target_domain='%s'
                         LIMIT 1""" % (sender_domain, sasl_sender_domain)
                logging.debug('SQL: query alias domains: %s' % sql)

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
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

            if allow_list_member:
                # Get alias members
                sql = """SELECT goto FROM alias
                         WHERE address='%s'
                         LIMIT 1""" % (sender)
                logging.debug('SQL: query members of alias account: %s' % sql)

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logging.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    members = sql_record[0].split(',')
                    if sasl_username in members:
                        logging.debug('Sender (%s) is member of mail alias (%s).' % (sasl_username, sender))
                        return SMTP_ACTIONS['default']
                else:
                    logging.debug('No such mail alias account.')

    return reject
