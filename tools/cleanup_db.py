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
from tools import debug, logger, get_db_conn, sql_count_id

web.config.debug = debug

backend = settings.backend
logger.info('* Backend: %s' % backend)

now = int(time.time())

conn_iredapd = get_db_conn('iredapd')

#
# Throttling
#
logger.info('-' * 40)
logger.info('* Remove expired throttle tracking records.')

# count existing records, delete, count left records
total_before = sql_count_id(conn_iredapd, 'throttle_tracking')
conn_iredapd.delete('throttle_tracking', where='init_time + period < %d' % now)
total_after = sql_count_id(conn_iredapd, 'throttle_tracking')

logger.info('  - %d removed, %d left.' % (total_before - total_after, total_after))

#
# Greylisting tracking records.
#
logger.info('-' * 40)
logger.info('* Remove expired greylisting tracking records.')

# count existing records, delete, count left records
total_before = sql_count_id(conn_iredapd, 'greylisting_tracking')
conn_iredapd.delete('greylisting_tracking', where='record_expired < %d' % now)
total_after = sql_count_id(conn_iredapd, 'greylisting_tracking')
logger.info('  - %d removed, %d left.' % (total_before - total_after, total_after))

#
# Some basic analyzation
#
# Count how many records are passed greylisting
qr = conn_iredapd.select('greylisting_tracking',
                         what='count(id) as total',
                         where='passed=1')
if qr:
    total_passed = qr[0].total
    logger.info('  - %d passed greylisting.' % (total_passed))

if total_after and settings.CLEANUP_SHOW_TOP_GREYLISTED_DOMAINS:
    top_num = settings.CLEANUP_NUM_OF_TOP_GREYLISTED_DOMAINS
    qr = conn_iredapd.select('greylisting_tracking',
                             what='count(id) as count, sender_domain',
                             group='sender_domain',
                             order='count DESC',
                             limit=top_num)
    if qr:
        logger.info('-' * 40)
        logger.info('* Top %d greylisted sender domains:' % top_num)
        logger.info('-' * 10)
        for r in qr:
            logger.info('%5d %s' % (r.count, r.sender_domain))

# TODO Count passed sender domain and whitelist its IP address with comment (domain name).
