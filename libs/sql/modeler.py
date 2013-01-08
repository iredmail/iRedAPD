# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
import settings
from libs import SMTP_ACTIONS, utils


class Modeler:
    def __init__(self):
        if settings.backend == 'mysql':
            import MySQLdb
            try:
                db = MySQLdb.connect(
                    host=settings.sql_server,
                    port=int(settings.sql_port),
                    db=settings.sql_db,
                    user=settings.sql_user,
                    passwd=settings.sql_password,
                )
                self.cursor = db.cursor()
            except Exception, e:
                logging.error("Error while creating database connection: %s" % str(e))
        elif settings.backend == 'pgsql':
            import psycopg2
            try:
                db = psycopg2.connect(
                    host=settings.sql_server,
                    port=int(settings.sql_port),
                    database=settings.sql_db,
                    user=settings.sql_user,
                    password=settings.sql_password,
                )
                self.cursor = db.cursor()
            except Exception, e:
                logging.error("Error while creating database connection: %s" % str(e))
        else:
            return SMTP_ACTIONS['default']

    def __del__(self):
        try:
            self.cursor.close()
            logging.debug('Closed SQL connection.')
        except Exception, e:
            logging.debug('Error while closing connection: %s' % str(e))

    def handle_data(self,
                    smtp_session_data,
                    plugins=[],
                    **kwargs
                   ):
        # No sender or recipient in smtp session.
        if not 'sender' in smtp_session_data or \
           not 'recipient' in smtp_session_data:
            return SMTP_ACTIONS['default']

        # Not a valid email address.
        if len(smtp_session_data['sender']) < 6:
            return 'DUNNO'

        # No plugins available.
        if not plugins:
            return 'DUNNO'

        plugin_kwargs = {'smtp_session_data': smtp_session_data,
                         'conn': self.cursor,
                         'sender': smtp_session_data['sender'],
                         'recipient': smtp_session_data['recipient'],
                         'sender_domain': smtp_session_data['sender'].split('@')[-1],
                         'recipient_domain': smtp_session_data['recipient'].split('@')[-1],
                        }

        # TODO Get SQL record of mail user or mail alias before applying plugins
        # TODO Query required sql columns instead of all

        for plugin in plugins:
            action = utils.apply_plugin(plugin, **plugin_kwargs)
            if not action.startswith('DUNNO'):
                return action

        return SMTP_ACTIONS['default']

