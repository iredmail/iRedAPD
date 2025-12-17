# Author: Zhang Huangbin <zhb _at_ iredmail.org>

from libs.logger import logger
import settings
from libs import SMTP_ACTIONS, utils
from libs.ldaplib import conn_utils


class Modeler:
    def __init__(self, conns):
        self.conns = conns
        self.conn = self.conns['conn_vmail']

    def handle_data(self,
                    smtp_session_data,
                    plugins=None,
                    sender_search_attrlist=None,
                    recipient_search_attrlist=None):
        if not plugins:
            return SMTP_ACTIONS['default'] + ' No enabled plugins'

        protocol_state = smtp_session_data['protocol_state'].upper()
        sender = smtp_session_data.get('sender', '')
        recipient = smtp_session_data.get('recipient', '')
        sasl_username = smtp_session_data.get('sasl_username', '')
        client_address = smtp_session_data.get('client_address', '')

        conn_amavisd = None
        if self.conns['conn_amavisd']:
            conn_amavisd = self.conns['conn_amavisd']

        conn_iredapd = None
        if self.conns['conn_iredapd']:
            conn_iredapd = self.conns['conn_iredapd']

        plugin_kwargs = {
            'smtp_session_data': smtp_session_data,
            'conn_vmail': self.conn,
            'conn_amavisd': conn_amavisd,
            'conn_iredapd': conn_iredapd,
            'sender': sender,
            'sender_without_ext': smtp_session_data['sender_without_ext'],
            'recipient': recipient,
            'recipient_without_ext': smtp_session_data['recipient_without_ext'],
            'client_address': client_address,
            'sasl_username': sasl_username,
            'sender_domain': smtp_session_data.get('sender_domain', ''),
            'recipient_domain': smtp_session_data.get('recipient_domain', ''),
            'sasl_username_domain': smtp_session_data.get('sasl_username_domain', ''),
            'base_dn': settings.ldap_basedn,
            'sender_dn': None,
            'sender_ldif': None,
            'recipient_dn': None,
            'recipient_ldif': None,
        }

        for plugin in plugins:
            # Get plugin target smtp protocol state
            try:
                target_protocol_state = plugin.SMTP_PROTOCOL_STATE
            except:
                target_protocol_state = ['RCPT']

            if protocol_state not in target_protocol_state:
                logger.debug("Skip plugin: {} (protocol_state != {})".format(plugin.__name__, protocol_state))
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

        # Close sql connections.
        try:
            if conn_amavisd:
                conn_amavisd.close()

            conn_iredapd.close()
        except:
            pass

        return SMTP_ACTIONS['default']
