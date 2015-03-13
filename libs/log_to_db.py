import logging
import settings

try:
    do_log = settings.log_action_in_db
except:
    do_log = False

def log_action(action, sender, recipient, ip, plugin_name):
    if not do_log:
        return None

    # Connect to db
    db_cursor = None
    if settings.backend in ['ldap', 'mysql']:
        import MySQLdb
        try:
            db = MySQLdb.connect(
                host=settings.log_db_server,
                port=int(settings.log_db_port),
                db=settings.log_db_name,
                user=settings.log_db_user,
                passwd=settings.log_db_password,
            )
            db_cursor = db.cursor()
        except Exception, e:
            logging.error("Error while connecting to log database: %s" % str(e))

    elif settings.backend == 'pgsql':
        import psycopg2
        try:
            db = psycopg2.connect(
                host=settings.log_db_server,
                port=int(settings.log_db_port),
                database=settings.log_db_name,
                user=settings.log_db_user,
                password=settings.log_db_password,
            )
            db_cursor = db.cursor()
        except Exception, e:
            logging.error("Error while connecting to log database: %s" % str(e))

    if not db_cursor:
        return None

    # Log action
    try:
        comment = '%s (%s -> %s, %s)' % (action, sender, recipient, plugin_name)
        sql = """INSERT INTO log (admin, ip, msg, timestamp) VALUES ('iredapd', '%s', '%s', NOW());
        """ % (ip, comment)

        logging.debug(sql)
        db_cursor.execute(sql)
    except Exception, e:
        logging.debug(e)
    finally:
        db.close()
        logging.debug('Close log database.')
