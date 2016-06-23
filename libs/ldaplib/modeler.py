# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import sys
import ldap
from libs.logger import logger
import settings
from libs import SMTP_ACTIONS, utils
from libs.ldaplib import conn_utils


class Modeler:
    def __init__(self, conns):
        # Initialize ldap connection.
        try:
            self.conn = ldap.initialize(settings.ldap_uri)
            logger.debug('LDAP connection initialied success.')
        except Exception, e:
            logger.error('LDAP initialized failed: %s.' % str(e))
            sys.exit()

        # Bind to ldap server.
        try:
            self.conn.bind_s(settings.ldap_binddn, settings.ldap_bindpw)
            logger.debug('LDAP bind success.')
        except ldap.INVALID_CREDENTIALS:
            logger.error('LDAP bind failed: incorrect bind dn or password.')
            sys.exit()
        except Exception, e:
            logger.error('LDAP bind failed: %s.' % str(e))
            sys.exit()

        self.conns = conns
        self.conns['conn_vmail'] = self.conn

    def __del__(self):
        try:
            self.conn.unbind_s()
            logger.debug('Close LDAP connection.')
        except Exception, e:
            logger.error('Error while closing connection: %s' % str(e))

    def handle_data(self,
                    smtp_session_data,
                    plugins=[],
                    sender_search_attrlist=[],
                    recipient_search_attrlist=[]):
        # No sender or recipient in smtp session.
        if 'sender' not in smtp_session_data or \
           'recipient' not in smtp_session_data:
            return SMTP_ACTIONS['default']

        # No plugins available.
        if not plugins:
            return 'DUNNO'

        protocol_state = smtp_session_data['protocol_state'].upper()
        sender = smtp_session_data.get('sender', '')
        recipient = smtp_session_data.get('recipient', '')
        sasl_username = smtp_session_data.get('sasl_username', '')
        client_address = smtp_session_data.get('client_address', '')

        conn_amavisd = None
        if self.conns['conn_amavisd']:
            conn_amavisd = self.conns['conn_amavisd'].connect()

        conn_iredapd = None
        if self.conns['conn_iredapd']:
            conn_iredapd = self.conns['conn_iredapd'].connect()

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn_vmail': self.conn,
                         'conn_amavisd': conn_amavisd,
                         'conn_iredapd': conn_iredapd,
                         'sender': sender,
                         'recipient': recipient,
                         'client_address': client_address,
                         'sasl_username': sasl_username,
                         'sender_domain': smtp_session_data.get('sender_domain', ''),
                         'recipient_domain': smtp_session_data.get('recipient_domain', ''),
                         'sasl_username_domain': smtp_session_data.get('sasl_username_domain', ''),
                         'base_dn': settings.ldap_basedn,
                         'sender_dn': None,
                         'sender_ldif': None,
                         'recipient_dn': None,
                         'recipient_ldif': None}

        for plugin in plugins:
            # Get plugin target smtp protocol state
            try:
                target_protocol_state = plugin.SMTP_PROTOCOL_STATE
            except:
                target_protocol_state = ['RCPT']

            if protocol_state not in target_protocol_state:
                logger.debug('Skip plugin: %s (protocol_state != %s)' % (plugin.__name__, protocol_state))
                continue

            # Get LDIF data of sender if required
            try:
                require_local_sender = plugin.REQUIRE_LOCAL_SENDER
            except:
                require_local_sender = False

            if require_local_sender and plugin_kwargs['sender_dn'] is None:
                sender_dn, sender_ldif = conn_utils.get_account_ldif(
                    conn=self.conn,
                    account=sasl_username,
                    attrs=sender_search_attrlist,
                )
                plugin_kwargs['sender_dn'] = sender_dn
                plugin_kwargs['sender_ldif'] = sender_ldif

            # Get LDIF data of recipient if required
            try:
                require_local_recipient = plugin.REQUIRE_LOCAL_RECIPIENT
            except:
                require_local_recipient = False

            if require_local_recipient and plugin_kwargs['recipient_dn'] is None:
                recipient_dn, recipient_ldif = conn_utils.get_account_ldif(
                    conn=self.conn,
                    account=recipient,
                    attrs=recipient_search_attrlist,
                )
                plugin_kwargs['recipient_dn'] = recipient_dn
                plugin_kwargs['recipient_ldif'] = recipient_ldif

            # Apply plugins
            action = utils.apply_plugin(plugin, **plugin_kwargs)

            if not action.startswith('DUNNO'):
                return action

        try:
            conn_amavisd.close()
            conn_iredapd.close()
        except:
            pass

        return SMTP_ACTIONS['default']
