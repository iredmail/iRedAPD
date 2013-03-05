# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import sys
import ldap
import logging
import settings
from libs import SMTP_ACTIONS, utils
from libs.ldaplib import conn_utils


class Modeler:
    def __init__(self):
        # Initialize ldap connection.
        try:
            self.conn = ldap.initialize(settings.ldap_uri)
            logging.debug('LDAP connection initialied success.')
        except Exception, e:
            logging.error('LDAP initialized failed: %s.' % str(e))
            sys.exit()

        # Bind to ldap server.
        try:
            self.conn.bind_s(settings.ldap_binddn, settings.ldap_bindpw)
            logging.debug('LDAP bind success.')
        except ldap.INVALID_CREDENTIALS:
            logging.error('LDAP bind failed: incorrect bind dn or password.')
            sys.exit()
        except Exception, e:
            logging.error('LDAP bind failed: %s.' % str(e))
            sys.exit()

    def __del__(self):
        try:
            self.conn.unbind_s()
            logging.debug('Close LDAP connection.')
        except Exception, e:
            logging.debug('Error while closing connection: %s' % str(e))

    def handle_data(self,
                    smtp_session_data,
                    plugins=[],
                    sender_search_attrlist=[],
                    recipient_search_attrlist=[]):
        # No sender or recipient in smtp session.
        if not 'sender' in smtp_session_data or \
                not 'recipient' in smtp_session_data:
            return SMTP_ACTIONS['default']

        # Not a valid email address.
        if len(smtp_session_data['sender']) < 6:
            return 'DUNNO'

        # No plugins available.
        if not plugins:
            return 'DUNNO'

        sender = smtp_session_data['sender'].lower()
        recipient = smtp_session_data['recipient'].lower()

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn': self.conn,
                         'base_dn': settings.ldap_basedn,
                         'sender': sender,
                         'sender_domain': sender.split('@', 1)[-1],
                         'recipient': recipient,
                         'recipient_domain': recipient.split('@', 1)[-1],
                         'sender_dn': None,
                         'sender_ldif': None,
                         'recipient_dn': None,
                         'recipient_ldif': None}

        # TODO Perform addition plugins which don't require sender/recipient info
        # e.g.
        #   - security enforce: encryption_protocol=TLSv1/SSLv3

        for plugin in plugins:
            # Get LDIF data of sender if required
            if plugin.REQUIRE_LOCAL_SENDER \
                    and plugin_kwargs['sender_dn'] is None:
                sender_dn, sender_ldif = conn_utils.get_account_ldif(
                    conn=self.conn,
                    account=sender,
                    attrlist=sender_search_attrlist,
                )
                plugin_kwargs['sender_dn'] = sender_dn
                plugin_kwargs['sender_ldif'] = sender_ldif

            # Get LDIF data of recipient if required
            if plugin.REQUIRE_LOCAL_RECIPIENT \
                    and plugin_kwargs['recipient_dn'] is None:
                recipient_dn, recipient_ldif = conn_utils.get_account_ldif(
                    conn=self.conn,
                    account=recipient,
                    attrlist=recipient_search_attrlist,
                )
                plugin_kwargs['recipient_dn'] = recipient_dn
                plugin_kwargs['recipient_ldif'] = recipient_ldif

            # Apply plugins
            action = utils.apply_plugin(plugin, **plugin_kwargs)
            if not action.startswith('DUNNO'):
                return action

        return SMTP_ACTIONS['default']
