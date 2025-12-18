# Author: Zhang Huangbin <zhb _at_ iredmail.org>

from libs.logger import logger
from libs import SMTP_ACTIONS, utils


class Modeler:
    def __init__(self, conns):
        # :param conns: a dict which contains pooled sql connections.
        self.conns = conns

    def handle_data(self,
                    smtp_session_data,
                    plugins=None,
                    **kwargs):
        if not plugins:
            return SMTP_ACTIONS['default'] + ' No enabled plugins'

        protocol_state = smtp_session_data['protocol_state'].upper()
        sender = smtp_session_data.get('sender', '')
        recipient = smtp_session_data.get('recipient', '')
        client_address = smtp_session_data.get('client_address', '')
        sasl_username = smtp_session_data.get('sasl_username', '')

        conn_vmail = self.conns['conn_vmail']

        engine_amavisd = None
        if self.conns['engine_amavisd']:
            engine_amavisd = self.conns['engine_amavisd']

        engine_iredapd = None
        if self.conns['engine_iredapd']:
            engine_iredapd = self.conns['engine_iredapd']

        plugin_kwargs = {
            'smtp_session_data': smtp_session_data,
            'conn_vmail': conn_vmail,
            'engine_amavisd': engine_amavisd,
            'engine_iredapd': engine_iredapd,
            'sender': sender,
            'sender_without_ext': smtp_session_data['sender_without_ext'],
            'recipient': recipient,
            'recipient_without_ext': smtp_session_data['recipient_without_ext'],
            'client_address': client_address,
            'sender_domain': smtp_session_data.get('sender_domain', ''),
            'recipient_domain': smtp_session_data.get('recipient_domain', ''),
            'sasl_username': sasl_username,
            'sasl_username_domain': smtp_session_data.get('sasl_username_domain', ''),
        }

        # TODO Get SQL record of mail user or mail alias before applying plugins
        # TODO Query required sql columns instead of all

        for plugin in plugins:
            # Get plugin target smtp protocol state
            try:
                target_protocol_state = plugin.SMTP_PROTOCOL_STATE
            except:
                target_protocol_state = ['RCPT']

            if protocol_state not in target_protocol_state:
                logger.debug("Skip plugin: {} (protocol_state != {})".format(plugin.__name__, protocol_state))
                continue

            action = utils.apply_plugin(plugin, **plugin_kwargs)

            if not action.startswith('DUNNO'):
                return action

        # Close sql connections.
        try:
            conn_vmail.close()
            engine_iredapd.close()

            if engine_amavisd:
                engine_amavisd.close()
        except:
            pass

        return SMTP_ACTIONS['default']
