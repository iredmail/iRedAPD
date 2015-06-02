# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
from libs import SMTP_ACTIONS, utils
from libs.utils import log_action


class Modeler:
    def __init__(self, conns, require_amavisd_db=False):
        # :param conns: a dict which contains pooled sql connections.
        self.conns = conns
        self.require_amavisd_db = require_amavisd_db

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

        conn_amavisd = None
        if self.require_amavisd_db:
            conn_amavisd = self.conns['conn_amavisd'].connect()

        conn_vmail = self.conns['conn_vmail'].connect()

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn_vmail': conn_vmail,
                         'conn_amavisd': conn_amavisd,
                         'sender': sender,
                         'recipient': recipient,
                         'sender_domain': sender.split('@')[-1],
                         'recipient_domain': recipient.split('@')[-1],
                         'sasl_username': sasl_username,
                         'amavisd_db_cursor': None}

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
                # Log action returned by plugin, except whitelist ('OK')
                if not action.startswith('OK') and self.conns['conn_iredadmin']:
                    conn_iredadmin = self.conns['conn_iredadmin'].connect()

                    log_action(conn=conn_iredadmin,
                               action=action,
                               sender=sender,
                               recipient=recipient,
                               ip=smtp_session_data['client_address'],
                               plugin_name=plugin.__name__)

                    conn_iredadmin.close()

                return action

        try:
            conn_vmail.close()
            conn_amavisd.close()
        except:
            pass

        return SMTP_ACTIONS['default']
