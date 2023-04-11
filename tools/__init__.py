"""Library used by other scripts under tools/ directory."""

# Author: Zhang Huangbin <zhb@iredmail.org>

import os
import sys
import time
import logging

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

import web
web.config.debug = False

import settings

backend = settings.backend
if backend in ['ldap', 'mysql']:
    sql_dbn = 'mysql'
elif backend in ['pgsql']:
    sql_dbn = 'postgres'
else:
    sys.exit('Error: Unsupported backend (%s).' % backend)

# logging
logger = logging.getLogger('iredapd-cmd')
_ch = logging.StreamHandler(sys.stdout)
_formatter = logging.Formatter('%(message)s')
_ch.setFormatter(_formatter)
logger.addHandler(_ch)

_log_level = getattr(logging, str(settings.log_level).upper())
logger.setLevel(_log_level)


def get_gmttime():
    # Convert local time to UTC
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())


def get_db_conn(db_name):
    try:
        conn = web.database(
            dbn=sql_dbn,
            host=settings.__dict__[db_name + '_db_server'],
            port=int(settings.__dict__[db_name + '_db_port']),
            db=settings.__dict__[db_name + '_db_name'],
            user=settings.__dict__[db_name + '_db_user'],
            pw=settings.__dict__[db_name + '_db_password'],
        )

        conn.supports_multiple_insert = True
        return conn
    except Exception as e:
        logger.error(e)


def sql_count_id(conn, table, column='id', where=None):
    if where:
        qr = conn.select(table,
                         what='count(%s) as total' % column,
                         where=where)
    else:
        qr = conn.select(table,
                         what='count(%s) as total' % column)
    if qr:
        total = qr[0].total
    else:
        total = 0

    return total


# Removing limited records each time from single table.
def cleanup_sql_table(conn,
                      sql_table,
                      unique_index_column='id',
                      sql_where=None,
                      print_left_rows=False):
    num_query_pages = 0
    num_removed_rows = 0

    loops = 0
    while True:
        remove_values = []
        _qr = conn.select(sql_table,
                          what="{}".format(unique_index_column),
                          where=sql_where,
                          limit=settings.CLEANUP_QUERY_SIZE_LIMIT)

        for i in _qr:
            remove_values.append(i[unique_index_column])

        if remove_values:
            num_query_pages += 1
            num_removed_rows += len(remove_values)

            conn.delete(sql_table,
                        vars={'values': remove_values},
                        where='{} IN $values'.format(unique_index_column))

            logger.info("* {:20}: {} records removed.".format(sql_table, num_removed_rows))
        else:
            break

        loops += 1

    if print_left_rows:
        _qr = conn.select(sql_table, what="COUNT({}) AS total".format(unique_index_column))
        total = _qr[0].total or 0

        logger.info("* {:20}: {} left.".format(sql_table, total))
