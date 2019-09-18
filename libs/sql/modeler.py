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
                         'sender_without_ext': utils.strip_mail_ext_address(sender),
                         'recipient': recipient,
                         'recipient_without_ext': utils.strip_mail_ext_address(recipient),
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
                target_protocol_state = plugin.SMTP_PROTOCOL_STATE
            except:
                target_protocol_state = ['RCPT']

            if protocol_state not in target_protocol_state:
                logger.debug('Skip plugin: %s (protocol_state != %s)' % (plugin.__name__, protocol_state))
                continue

            action = utils.apply_plugin(plugin, **plugin_kwargs)

            if not (action.startswith('DUNNO') or action.startswith('PREPEND')):
                return action

        # Close sql connections.
        try:
            conn_vmail.close()
            conn_amavisd.close()
            conn_iredapd.close()
        except:
            pass

        return SMTP_ACTIONS['default']
