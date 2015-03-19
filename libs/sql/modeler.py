# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
import settings
from libs import SMTP_ACTIONS, utils
from libs.amavisd import core as amavisd_lib
from libs.log_to_db import log_action


class Modeler:
    def __init__(self):
        if settings.backend == 'mysql':
            import MySQLdb
            try:
                self.db = MySQLdb.connect(
                    host=settings.sql_server,
                    port=int(settings.sql_port),
                    db=settings.sql_db,
                    user=settings.sql_user,
                    passwd=settings.sql_password,
                )
                self.cursor = self.db.cursor()
            except Exception, e:
                logging.error("Error while creating database connection: %s" % str(e))
        elif settings.backend == 'pgsql':
            import psycopg2
            try:
                self.db = psycopg2.connect(
                    host=settings.sql_server,
                    port=int(settings.sql_port),
                    database=settings.sql_db,
                    user=settings.sql_user,
                    password=settings.sql_password,
                )
                self.cursor = self.db.cursor()
            except Exception, e:
                logging.error("Error while creating database connection: %s" % str(e))
        else:
            return SMTP_ACTIONS['default']

    def __del__(self):
        try:
            self.db.close()
            logging.debug('Closed SQL connection.')
        except Exception, e:
            logging.debug('Error while closing connection: %s' % str(e))

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
                         'conn': self.cursor,
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

            # Connect to Amavisd database if required
            try:
                plugin_require_amavisd_db = plugin.REQUIRE_AMAVISD_DB
            except:
                plugin_require_amavisd_db = False

            if plugin_require_amavisd_db:
                if not plugin_kwargs['amavisd_db_cursor']:
                    try:
                        amavisd_db_wrap = amavisd_lib.AmavisdDBWrap()
                        plugin_kwargs['amavisd_db_cursor'] = amavisd_db_wrap.cursor
                        logging.debug('Got db cursor.')
                    except Exception, e:
                        logging.debug('Skip plugin, error while getting db cursor: %s' % str(e))
                        continue

            action = utils.apply_plugin(plugin, **plugin_kwargs)
            if not (action.startswith('DUNNO') or action.startswith('OK')):
                # Log action
                log_action(action=action,
                           sender=sender,
                           recipient=recipient,
                           ip=smtp_session_data['client_address'],
                           plugin_name=plugin.__name__)

                return action

        return SMTP_ACTIONS['default']
