#!/usr/bin/env python3

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Cleanup expired throttle and greylisting tracking records.

import os
import sys
import time
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

import settings
from tools import get_db_conn, cleanup_sql_table

web.config.debug = False

backend = settings.backend
now = int(time.time())
conn_iredapd = get_db_conn('iredapd')

#
# Throttling
#
cleanup_sql_table(conn=conn_iredapd,
                  sql_table='throttle_tracking',
                  sql_where='(init_time + period) < %d' % now,
                  print_left_rows=True)

#
# Greylisting tracking records.
#
cleanup_sql_table(conn=conn_iredapd,
                  sql_table='greylisting_tracking',
                  sql_where='record_expired < %d' % now,
                  print_left_rows=True)

#
# Clean up cached senderscore results.
#
expire_seconds = int(time.time()) - (settings.SENDERSCORE_CACHE_DAYS * 86400)
cleanup_sql_table(conn=conn_iredapd,
                  sql_table='senderscore_cache',
                  unique_index_column='client_address',
                  sql_where='time < %d' % expire_seconds,
                  print_left_rows=True)

#
# Clean up `smtp_sessions`
#
expire_seconds = int(time.time()) - (settings.LOG_SMTP_SESSIONS_EXPIRE_DAYS * 86400)
cleanup_sql_table(conn=conn_iredapd,
                  sql_table='smtp_sessions',
                  sql_where='time_num < %d' % expire_seconds,
                  print_left_rows=True)
