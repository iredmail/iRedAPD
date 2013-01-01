# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import sys
import ldap
import logging
import settings
from libs import SMTP_ACTIONS
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

    def handle_data(self, smtp_session_map,
                    plugins=[],
                    plugins_for_sender=[],
                    plugins_for_recipient=[],
                    plugins_for_misc=[],
                    sender_search_attrlist=None,
                    recipient_search_attrlist=None,
                    ):
        # No sender or recipient in smtp session.
        if not 'sender' in smtp_session_map or not 'recipient' in smtp_session_map:
            return SMTP_ACTIONS['defer']

        # Not a valid email address.
        if len(smtp_session_map['sender']) < 6:
            return 'DUNNO'

        # No plugins available.
        if not plugins:
            return 'DUNNO'

        # Check whether we should get sender/recipient LDIF data first
        get_sender_ldif = False
        get_recipient_ldif = False
        if plugins_for_sender:
            get_sender_ldif = True

        if plugins_for_recipient:
            get_recipient_ldif = True

        # Get account dn and LDIF data.
        plugin_kwargs = {'smtpSessionData': smtp_session_map,
                         'conn': self.conn,
                         'baseDn': settings.ldap_basedn,
                         'senderDn': None,
                         'senderLdif': None,
                         'recipientDn': None,
                         'recipientLdif': None,
                         }

        if get_sender_ldif:
            senderDn, senderLdif = conn_utils.get_account_ldif(
                conn=self.conn,
                account=smtp_session_map['sender'],
                attrlist=sender_search_attrlist,
            )
            plugin_kwargs['senderDn'] = senderDn
            plugin_kwargs['senderLdif'] = senderLdif

            for plugin in plugins_for_sender:
                action = conn_utils.apply_plugin(plugin, **plugin_kwargs)
                if not action.startswith('DUNNO'):
                    return action

        if get_recipient_ldif:
            recipientDn, recipientLdif = conn_utils.get_account_ldif(
                conn=self.conn,
                account=smtp_session_map['recipient'],
                attrlist=recipient_search_attrlist,
            )
            plugin_kwargs['recipientDn'] = recipientDn
            plugin_kwargs['recipientLdif'] = recipientLdif

            for plugin in plugins_for_recipient:
                action = conn_utils.apply_plugin(plugin, **plugin_kwargs)
                if not action.startswith('DUNNO'):
                    return action

        for plugin in plugins_for_misc:
            action = conn_utils.apply_plugin(plugin, **plugin_kwargs)
            if not action.startswith('DUNNO'):
                return action

        return SMTP_ACTIONS['default']
