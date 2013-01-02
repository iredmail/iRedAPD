# Author: Zhang Huangbin <zhb _at_ iredmail.org>

import logging
from libs import SMTP_ACTIONS


class Modeler:
    def __init__(self, cfg):
        self.cfg = cfg

        # Backend
        self.backend = self.cfg.get('general', 'backend', 'mysql')

        if self.backend == 'mysql':
            import MySQLdb
            try:
                db = MySQLdb.connect(
                    host=self.cfg.get('sql', 'server', 'localhost'),
                    db=self.cfg.get('sql', 'db', 'vmail'),
                    user=self.cfg.get('sql', 'user', 'vmail'),
                    passwd=self.cfg.get('sql', 'password'),
                )
                self.cursor = db.cursor()
            except Exception, e:
                logging.error("Error while creating database connection: %s" % str(e))
        elif self.backend == 'pgsql':
            import psycopg2
            try:
                db = psycopg2.connect(
                    host=self.cfg.get('sql', 'server', 'localhost'),
                    port=self.cfg.get('sql', 'port', '5432'),
                    database=self.cfg.get('sql', 'db', 'vmail'),
                    user=self.cfg.get('sql', 'user', 'vmail'),
                    password=self.cfg.get('sql', 'password'),
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

    def handle_data(self, smtp_session_data, plugins=[]):
        if 'sender' in smtp_session_data.keys() and 'recipient' in smtp_session_data.keys():
            if len(smtp_session_data['sender']) < 6:
                # Not a valid email address.
                return 'DUNNO'

            # Get plugin module name and convert plugin list to python list type.
            self.plugins = self.cfg.get('sql', 'plugins', '')
            self.plugins = [v.strip() for v in self.plugins.split(',')]

            # Get sender, recipient.
            # Sender/recipient are used almost in all plugins, so store them
            # a dict and pass to plugins.
            senderReceiver = {
                'sender': smtp_session_data['sender'],
                'recipient': smtp_session_data['recipient'],
                'sender_domain': smtp_session_data['sender'].split('@')[-1],
                'recipient_domain': smtp_session_data['recipient'].split('@')[-1],
            }

            if len(self.plugins) > 0:
                #
                # Import plugin modules.
                #
                self.modules = []

                # Load plugin module.
                for plugin in self.plugins:
                    try:
                        self.modules.append(__import__(plugin))
                    except ImportError:
                        # Print error message if plugin module doesn't exist.
                        # Use logging.info to let admin know this critical error.
                        logging.info('Error: plugin %s.py not exist.' % plugin)
                    except Exception, e:
                        logging.debug('Error while importing plugin module (%s): %s' % (plugin, str(e)))

                #
                # Apply plugins.
                #
                self.action = ''
                for module in self.modules:
                    try:
                        logging.debug('Apply plugin: %s.' % (module.__name__, ))
                        pluginAction = module.restriction(
                            dbConn=self.cursor,
                            senderReceiver=senderReceiver,
                            smtp_session_data=smtp_session_data,
                        )

                        logging.debug('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                        if not pluginAction.startswith('DUNNO'):
                            logging.info('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                            return pluginAction
                    except Exception, e:
                        logging.debug('Error while apply plugin (%s): %s' % (module, str(e)))

            else:
                # No plugins available.
                return 'DUNNO'
        else:
            return SMTP_ACTIONS['defer']

