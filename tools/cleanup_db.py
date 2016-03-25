#!/usr/bin/env python

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
from tools import logger, get_db_conn, sql_count_id


def print_top_greylisting_domains(conn, limit=30, passed=False):
    if not limit:
        limit = settings.CLEANUP_NUM_OF_TOP_GREYLISTED_DOMAINS

    sql_where = 'passed=0'
    banner = '* Top %d sender_domains which not yet passed greylisting:' % limit
    if passed:
        sql_where = 'passed=1'
        banner = '* Top %d sender_domains which already passed greylisting:' % limit

    qr = conn.select('greylisting_tracking',
                     what='count(id) as count, sender_domain, client_address',
                     where=sql_where,
                     group='sender_domain',
                     order='count DESC',
                     limit=limit)

    if qr:
        logger.info(banner)

        for r in qr:
            logger.info('\t%5d %s  [%s]' % (r.count, r.sender_domain, r.client_address))


web.config.debug = False

backend = settings.backend
logger.info('* Backend: %s' % backend)

now = int(time.time())

conn_iredapd = get_db_conn('iredapd')

#
# Throttling
#
logger.info('* Remove expired throttle tracking records.')

# count existing records, delete, count left records
total_before = sql_count_id(conn_iredapd, 'throttle_tracking')
conn_iredapd.delete('throttle_tracking', where='init_time + period < %d' % now)
total_after = sql_count_id(conn_iredapd, 'throttle_tracking')

logger.info('\t- %d removed, %d left.' % (total_before - total_after, total_after))

#
# Greylisting tracking records.
#
logger.info('* Remove expired greylisting tracking records.')

# count existing records, delete, count left records
total_before = sql_count_id(conn_iredapd, 'greylisting_tracking')
conn_iredapd.delete('greylisting_tracking', where='record_expired < %d' % now)
total_after = sql_count_id(conn_iredapd, 'greylisting_tracking')

#
# Some basic analyzation
#
# Count how many records are passed greylisting
total_passed = 0
qr = conn_iredapd.select('greylisting_tracking',
                         what='count(id) as total',
                         where='passed=1')
if qr:
    total_passed = qr[0].total

logger.info('\t- %d removed, %d left (%d passed, %d not).' % (
    total_before - total_after,
    total_after,
    total_passed,
    total_after - total_passed))

# Show top senders which not yet passed greylisting.
top_limit = settings.CLEANUP_NUM_OF_TOP_GREYLISTED_DOMAINS
if total_after and settings.CLEANUP_SHOW_TOP_GREYLISTED_DOMAINS:
    print_top_greylisting_domains(conn=conn_iredapd, limit=top_limit, passed=False)

# Show top senders which already passed greylisting.
if total_after and settings.CLEANUP_SHOW_TOP_GREYLISTED_DOMAINS:
    print_top_greylisting_domains(conn=conn_iredapd, limit=top_limit, passed=True)

# SQL condition used to query `log_sasl` and `log_smtp_actions`.
if settings.backend in ['ldap', 'mysql']:
    sql_where_timestamp = 'timestamp < DATE_SUB(NOW(), INTERVAL %d DAY)'
elif settings.backend in ['pgsql']:
    sql_where_timestamp = "timestamp < CURRENT_TIMESTAMP - INTERVAL '%d DAY'"

#
# Remove old records in `log_smtp_actions` table
#
kept_days = settings.CLEANUP_KEEP_ACTION_LOG_DAYS
logger.info('* Remove old (> %d days) records in `log_smtp_actions`.' % kept_days)

total_before = sql_count_id(conn_iredapd, 'log_smtp_actions')
conn_iredapd.delete('log_smtp_actions', where=sql_where_timestamp % kept_days)
total_after = sql_count_id(conn_iredapd, 'log_smtp_actions')

logger.info('\t- %d removed, %d left.' % (total_before - total_after, total_after))

#
# Remove old records in `log_sasl` table
#
kept_days = settings.CLEANUP_KEEP_SASL_LOG_DAYS
logger.info('* Remove old (> %d days) records in `log_sasl`.' % kept_days)

total_before = sql_count_id(conn_iredapd, 'log_sasl')
conn_iredapd.delete('log_sasl', where=sql_where_timestamp % kept_days)
total_after = sql_count_id(conn_iredapd, 'log_sasl')

logger.info('\t- %d removed, %d left.' % (total_before - total_after, total_after))
