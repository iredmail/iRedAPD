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
#   Settings applied on message sent by not-authenticated user:
#
#   1) Check whether sender address is forged. If sender domain is hosted
#      locally, smtp authentication is required, so sender will be considered
#      as forged address. Default value is True.
#
#       CHECK_FORGED_SENDER = True
#
#   2) If you want to allow someone to send email as forged address, e.g.
#      salesforce.com, you can bypass these addresses in this setting.
#      Default value is empty (no allowed forged sender).
#
#       ALLOWED_FORGED_SENDERS = ['user@local_domain1.com', 'local_domain2.com']
#
#      With above setting, if sender is 'user@local.com', this plugin won't
#      reject it.
#
#   Settings applied on message sent by authenticated user:
#
#   1) List senders who are allowed to send email as different
#      users in iRedAPD config file (/opt/iredapd/settings.py).
#      Valid sender format:
#
#       - full email address. e.g. `user@domain.ltd`.
#
#           Allow this sender to send email as ANY sender address.
#
#       - domain name. e.g. `domain.ltd`.
#
#           Allow all users under this domain to send email as ANY sender address.
#
#       - @ + domain name. e.g. `@domain.ltd`.
#
#           Allow all users under this domain to send email as sender address
#           under the same domain.
#
#       - catch-all address: '@.'
#
#           All all users hosted on this server to send email as sender address
#           under the same domain.
#
#      Sample setting:
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

from libs.logger import logger
from libs import SMTP_ACTIONS
from libs.utils import is_trusted_client
import settings

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import is_local_domain
else:
    from libs.sql import is_local_domain


check_forged_sender = settings.CHECK_FORGED_SENDER
allowed_forged_sender = settings.ALLOWED_FORGED_SENDERS
allowed_senders = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
is_strict = settings.ALLOWED_LOGIN_MISMATCH_STRICTLY
allow_list_member = settings.ALLOWED_LOGIN_MISMATCH_LIST_MEMBER

if is_strict or allow_list_member:
    if settings.backend == 'ldap':
        from libs.ldaplib import conn_utils

action_reject = SMTP_ACTIONS['reject_sender_login_mismatch']


def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']

    sasl_username_user = sasl_username.split('@', 1)[0]
    sasl_username_domain = kwargs['sasl_username_domain']

    sender = kwargs['sender']
    sender_name = ''
    sender_domain = ''
    if sender:
        (sender_name, sender_domain) = sender.split('@', 1)

    recipient_domain = kwargs['recipient_domain']
    client_address = kwargs['client_address']

    real_sasl_username = sasl_username
    real_sender = sender

    conn = kwargs['conn_vmail']

    # Check emails sent from external network.
    if not sasl_username:
        logger.debug('Not an authenticated sender (no sasl_username).')

        # Bypass localhost.
        # NOTE: if sender sent email through SOGo, smtp session may not
        #       have sasl_username.
        if is_trusted_client(client_address):
            return SMTP_ACTIONS['default']

        if not check_forged_sender:
            return SMTP_ACTIONS['default']
        else:
            # Bypass allowed forged sender.
            if sender in allowed_forged_sender or sender_domain in allowed_forged_sender:
                return SMTP_ACTIONS['default']

            sender_is_forged = False
            if sender_domain == recipient_domain:
                # domain is hosted locally, sender must login first.
                logger.debug('Sender is forged address (sender domain == recipient domain).')
                sender_is_forged = True
            else:
                # Check whether sender domain is hosted on localhost
                if is_local_domain(conn=conn, domain=sender_domain):
                    sender_is_forged = True

            if sender_is_forged:
                return SMTP_ACTIONS['reject'] + ' not logged in'
            else:
                logger.debug('Sender domain is not hosted locally.')
                return SMTP_ACTIONS['default']

    # Check emails sent by authenticated users.
    logger.debug('Sender: %s, SASL username: %s' % (sender, sasl_username))

    if sender == sasl_username:
        logger.debug('SKIP: sender == sasl username.')
        return SMTP_ACTIONS['default']

    #
    # sender != sasl_username
    #
    # If no access settings available, reject directly.
    if not (allowed_senders or is_strict or allow_list_member):
        logger.debug('No allowed senders in config file.')
        return action_reject

    # Check explicitly allowed senders
    if allowed_senders:
        logger.debug('Allowed SASL senders: %s' % ', '.join(allowed_senders))
        if sasl_username in allowed_senders:
            logger.debug('Sender SASL username is explicitly allowed.')
            return SMTP_ACTIONS['default']
        elif sasl_username_domain in allowed_senders:
            logger.debug('Sender domain name is explicitly allowed.')
            return SMTP_ACTIONS['default']
        elif ('@' + sasl_username_domain in allowed_senders) or ('@.' in allowed_senders):
            # Restrict to send as users under SAME domain
            if sasl_username_domain == sender_domain:
                return SMTP_ACTIONS['default']
        else:
            # Note: not reject email here, still need to check other access settings.
            logger.debug('Sender is not allowed to send email as other user (ALLOWED_LOGIN_MISMATCH_SENDERS).')

    # Check alias domains and user alias addresses
    if is_strict or allow_list_member:
        if is_strict:
            logger.debug('Apply strict restriction (ALLOWED_LOGIN_MISMATCH_STRICTLY=True).')

        if allow_list_member:
            logger.debug('Apply list/alias member restriction (ALLOWED_LOGIN_MISMATCH_LIST_MEMBER=True).')

        if settings.backend == 'ldap':
            filter_user_alias = '(&(objectClass=mailUser)(mail=%s)(shadowAddress=%s))' % (sasl_username, sender)
            filter_list_member = '(&(objectClass=mailUser)(|(mail=%s)(shadowAddress=%s))(memberOfGroup=%s))' % (sasl_username, sasl_username, sender)
            filter_alias_member = '(&(objectClass=mailAlias)(|(mail=%s)(shadowAddress=%s))(mailForwardingAddress=%s))' % (sender, sender, sasl_username)

            if is_strict and (not allow_list_member):
                # Query mail account directly
                query_filter = filter_user_alias
                success_msg = 'Sender is an user alias address.'
            elif (not is_strict) and allow_list_member:
                query_filter = '(|' + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender (%s) is member of mail list/alias (%s).' % (sasl_username, sender)
            else:
                # (is_strict and allow_list_member)
                query_filter = '(|' + filter_user_alias + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender (%s) is an user alias address or list/alias member (%s).' % (sasl_username, sender)

            qr = conn_utils.get_account_ldif(
                conn=conn,
                account=sasl_username,
                query_filter=query_filter,
                attrs=['dn'],
            )
            (dn, entry) = qr
            if dn:
                logger.debug(success_msg)
                return SMTP_ACTIONS['default']
            else:
                logger.debug('Sender is either an user alias address or list/alias member.')
                return action_reject

        elif settings.backend in ['mysql', 'pgsql']:
            if is_strict:
                # Get alias domains
                sql = """SELECT alias_domain
                           FROM alias_domain
                          WHERE alias_domain='%s' AND target_domain='%s'
                          LIMIT 1""" % (sender_domain, sasl_username_domain)
                logger.debug('[SQL] query alias domains: \n%s' % sql)

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logger.debug('SQL query result: %s' % str(sql_record))

                if not sql_record:
                    logger.debug('No alias domain found.')
                else:
                    logger.debug('Sender domain %s is an alias domain of %s.' % (sender_domain, sasl_username_domain))

                    real_sasl_username = sasl_username_user + '@' + sasl_username_domain
                    real_sender = sender_name + '@' + sasl_username_domain

                    # sender_domain is one of alias domains
                    if sender_name != sasl_username_user:
                        logger.debug('Sender is not an user alias address.')
                    else:
                        logger.debug('Sender is an alias address of sasl username.')
                        return SMTP_ACTIONS['default']

            if allow_list_member:
                # Get alias members
                sql = """SELECT goto
                           FROM alias
                          WHERE address='%s'
                          LIMIT 1""" % (real_sender)
                logger.debug('[SQL] query members of alias account (%s): \n%s' % (real_sender, sql))

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logger.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    members = sql_record[0].split(',')
                    if (sasl_username in members) or (real_sasl_username in members):
                        logger.debug('SASL username (%s) is a member of mail alias (%s).' % (sasl_username, sender))
                        return SMTP_ACTIONS['default']
                else:
                    logger.debug('No such mail alias account.')

    return action_reject
