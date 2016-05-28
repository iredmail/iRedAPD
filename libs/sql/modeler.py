# Author: Zhang Huangbin <zhb _at_ iredmail.org>

from libs.logger import logger
from libs import SMTP_ACTIONS, utils


class Modeler:
    def __init__(self, conns):
        # :param conns: a dict which contains pooled sql connections.
        self.conns = conns

    def handle_data(self,
                    smtp_session_data,
                    plugins=[],
                    **kwargs):
        # No sender or recipient in smtp session.
        if not 'sender' in smtp_session_data or \
           not 'recipient' in smtp_session_data:
            return SMTP_ACTIONS['default']

        # No plugins available.
        if not plugins:
            return 'DUNNO'

        smtp_protocol_state = smtp_session_data['protocol_state'].upper()
        sender = smtp_session_data.get('sender', '')
        recipient = smtp_session_data.get('recipient', '')
        client_address = smtp_session_data.get('client_address', '')

        conn_vmail = self.conns['conn_vmail'].connect()

        conn_amavisd = None
        if self.conns['conn_amavisd']:
            conn_amavisd = self.conns['conn_amavisd'].connect()

        conn_iredapd = None
        if self.conns['conn_iredapd']:
            conn_iredapd = self.conns['conn_iredapd'].connect()

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn_vmail': conn_vmail,
                         'conn_amavisd': conn_amavisd,
                         'conn_iredapd': conn_iredapd,
                         'sender': sender,
                         'recipient': recipient,
                         'client_address': client_address,
                         'sender_domain': smtp_session_data.get('sender_domain', ''),
                         'recipient_domain': smtp_session_data.get('recipient_domain', ''),
                         'sasl_username': smtp_session_data.get('sasl_username', ''),
                         'sasl_username_domain': smtp_session_data.get('sasl_username_domain', '')}

        # TODO Get SQL record of mail user or mail alias before applying plugins
        # TODO Query required sql columns instead of all

        for plugin in plugins:
            # Get plugin target smtp protocol state
            try:
                target_smtp_protocol_state = plugin.SMTP_PROTOCOL_STATE
            except:
                target_smtp_protocol_state = ['RCPT']

            if not smtp_protocol_state in target_smtp_protocol_state:
                logger.debug('Skip plugin: %s (protocol_state != %s)' % (plugin.__name__, smtp_protocol_state))
                continue

            action = utils.apply_plugin(plugin, **plugin_kwargs)
            if not action.startswith('DUNNO'):
                return action

        try:
            conn_vmail.close()
        except:
            pass

        try:
            conn_amavisd.close()
        except:
            pass

        try:
            conn_iredapd.close()
        except:
            pass

        return SMTP_ACTIONS['default']
