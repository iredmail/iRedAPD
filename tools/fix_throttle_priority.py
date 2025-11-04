#!/usr/bin/env python3

# Author: ly020044
# Purpose: Fix priority field in throttle table based on account type.

# Usage:
#
#   1) Run this script to fix priority field in throttle table based on account type.
#
#   2) Run command:
#
#       python3 fix_throttle_priority.py

import os
import sys

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

import web
web.config.debug = False

from libs.utils import get_account_priority
from tools import get_db_conn, sql_count_id

# Set the number of records to process per page
batch_size = 100

# Connect to iredapd database
conn_iredapd = get_db_conn('iredapd')
if not conn_iredapd:
    print("ERROR: Failed to connect to iredapd database.")
    sys.exit(1)

try:
    # Get total number of records
    total_count = sql_count_id(conn=conn_iredapd, table='throttle')
    if not total_count:
        print("No throttle settings, no need to fix. Skip.")
        sys.exit(0)

    updated_records = 0
    processed = 0
    page = 1

    # Process data in pages
    while processed < total_count:
        # Use conn.select instead of conn.execute for better SQLAlchemy 2.0 compatibility
        rows = conn_iredapd.select('throttle',
                                   what='id, account, priority',
                                   order='id',
                                   limit=batch_size,
                                   offset=processed)

        if not rows:
            break

        for row in rows:
            expected_priority = get_account_priority(row.account)

            if row.priority != expected_priority:
                conn_iredapd.update('throttle',
                                    where='id=$id',
                                    vars={'id': row.id},
                                    priority=expected_priority)

                print(f"Fixed throttle priority: account={row.account}, priority: {row.priority} -> {expected_priority}.")
                updated_records += 1

        processed += len(rows)
        page += 1
except Exception as e:
    print(f"ERROR: An error occurred: {str(e)}")
    sys.exit(255)
finally:
    pass
