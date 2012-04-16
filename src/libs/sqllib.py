from libs import SMTP_ACTIONS


class SQLModeler:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger

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
                self.logger.error("Error while creating database connection: %s" % str(e))
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
                self.logger.error("Error while creating database connection: %s" % str(e))
        else:
            return SMTP_ACTIONS['default']

    def __del__(self):
        try:
            self.cursor.close()
            self.logger.debug('Closed SQL connection.')
        except Exception, e:
            self.logger.debug('Error while closing connection: %s' % str(e))

    def handle_data(self, map):
        if 'sender' in map.keys() and 'recipient' in map.keys():
            if len(map['sender']) < 6:
                # Not a valid email address.
                return 'DUNNO'

            # Get plugin module name and convert plugin list to python list type.
            self.plugins = self.cfg.get('sql', 'plugins', '')
            self.plugins = [v.strip() for v in self.plugins.split(',')]

            # Get sender, recipient.
            # Sender/recipient are used almost in all plugins, so store them
            # a dict and pass to plugins.
            senderReceiver = {
                'sender': map['sender'],
                'recipient': map['recipient'],
                'sender_domain': map['sender'].split('@')[-1],
                'recipient_domain': map['recipient'].split('@')[-1],
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
                        # Use self.logger.info to let admin know this critical error.
                        self.logger.info('Error: plugin %s.py not exist.' % plugin)
                    except Exception, e:
                        self.logger.debug('Error while importing plugin module (%s): %s' % (plugin, str(e)))

                #
                # Apply plugins.
                #
                self.action = ''
                for module in self.modules:
                    try:
                        self.logger.debug('Apply plugin (%s).' % (module.__name__, ))
                        pluginAction = module.restriction(
                            dbConn=self.cursor,
                            senderReceiver=senderReceiver,
                            smtpSessionData=map,
                            logger=self.logger,
                        )

                        self.logger.debug('Response (%s): %s' % (module.__name__, pluginAction))
                        if not pluginAction.startswith('DUNNO'):
                            self.logger.info('Response (%s): %s' % (module.__name__, pluginAction))
                            return pluginAction
                    except Exception, e:
                        self.logger.debug('Error while apply plugin (%s): %s' % (module, str(e)))

            else:
                # No plugins available.
                return 'DUNNO'
        else:
            return SMTP_ACTIONS['defer']

