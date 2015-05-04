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
        smtp_protocol_state = smtp_session_data['protocol_state'].upper()

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn_vmail': self.conns['conn_vmail'].connect(),
                         'conn_amavisd': self.conns['conn_amavisd'].connect(),
                         #'conn_iredadmin': self.conns['conn_iredadmin'].connect(),
                         'sender': sender,
                         'recipient': recipient,
                         'sender_domain': sender.split('@')[-1],
                         'recipient_domain': recipient.split('@')[-1],
                         'sasl_username': sasl_username,
                         'amavisd_db_cursor': None}

        logging.debug('Keyword arguments passed to plugin: %s' % str(plugin_kwargs))

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
            if not (action.startswith('DUNNO') or action.startswith('OK')):
                # Log action
                if self.conns['conn_iredadmin']:
                    log_action(conn=self.conns['conn_iredadmin'].connect(),
                               action=action,
                               sender=sender,
                               recipient=recipient,
                               ip=smtp_session_data['client_address'],
                               plugin_name=plugin.__name__)

                return action

        return SMTP_ACTIONS['default']
