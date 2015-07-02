# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
from libs import SMTP_ACTIONS, utils
from libs.utils import log_action


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

        sender = smtp_session_data['sender'].lower()
        recipient = smtp_session_data['recipient'].lower()
        sasl_username = smtp_session_data['sasl_username'].lower()
        sasl_username_domain = sasl_username.split('@', 1)[-1]
        smtp_protocol_state = smtp_session_data['protocol_state'].upper()

        conn_vmail = self.conns['conn_vmail'].connect()

        conn_amavisd = None
        if self.conns['conn_amavisd']:
            conn_amavisd = self.conns['conn_amavisd'].connect()

        conn_iredapd = None
        if self.conns['conn_iredapd']:
            conn_iredapd = self.conns['conn_iredapd'].connect()

        conn_iredadmin = None
        if self.conns['conn_iredadmin']:
            conn_iredadmin = self.conns['conn_iredadmin'].connect()

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn_vmail': conn_vmail,
                         'conn_amavisd': conn_amavisd,
                         'conn_iredapd': conn_iredapd,
                         'sender': sender,
                         'sender_domain': sender.split('@')[-1],
                         'recipient': recipient,
                         'recipient_domain': recipient.split('@')[-1],
                         'sasl_username': sasl_username,
                         'sasl_username_domain': sasl_username_domain}

        # TODO Get SQL record of mail user or mail alias before applying plugins
        # TODO Query required sql columns instead of all

        for plugin in plugins:
            # Get plugin target smtp protocol state
            try:
                target_smtp_protocol_state = plugin.SMTP_PROTOCOL_STATE
            except:
                target_smtp_protocol_state = 'RCPT'

            if smtp_protocol_state != target_smtp_protocol_state:
                logging.debug('Skip plugin: %s (protocol_state != %s)' % (plugin.__name__, smtp_protocol_state))
                continue

            action = utils.apply_plugin(plugin, **plugin_kwargs)
            if not action.startswith('DUNNO'):
                # Log action returned by plugin
                log_action(conn=conn_iredadmin,
                           action=action,
                           sender=sender,
                           recipient=recipient,
                           ip=smtp_session_data['client_address'],
                           plugin_name=plugin.__name__)

                return action

        try:
            conn_vmail.close()
            conn_amavisd.close()
            conn_iredapd.close()
            conn_iredadmin.close()
        except:
            pass

        return SMTP_ACTIONS['default']
