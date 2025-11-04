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

import settings
from libs.utils import get_account_priority
from tools import get_db_conn, sql_count_id

# Set the number of records to process per page
batch_size = 1000

# Connect to iredapd database
conn_iredapd = get_db_conn('iredapd')
if not conn_iredapd:
    print("ERROR: Failed to connect to database.")
    sys.exit(1)

try:
    # Get total number of records
    total_count = sql_count_id(conn=conn_iredapd, table='throttle')
    print(f"Total records to process: {total_count}")
    print("--------------------------------")
    
    total_records = 0
    updated_records = 0
    processed = 0
    page = 1
    
    # Process data in pages
    while processed < total_count:
        print(f"Processing page {page} ({processed+1} to {min(processed+batch_size, total_count)})")
        
        # Use conn.select instead of conn.execute for better SQLAlchemy 2.0 compatibility
        rows = conn_iredapd.select('throttle',
                                  what='id, account, priority',
                                  order='id',
                                  limit=batch_size,
                                  offset=processed)
        
        if not rows:
            break
        
        # Process records on current page
        for row in rows:
            total_records += 1
            rec_id = row.id
            account = row.account
            current_priority = row.priority
            
            # Get correct priority based on account type using existing function
            correct_priority = get_account_priority(account)
            
            # Update if priority is incorrect
            if current_priority != correct_priority:
                conn_iredapd.update('throttle',
                                   where='id=$id',
                                   vars={'id': rec_id},
                                   priority=correct_priority)
                updated_records += 1
                # Show progress every 100 updated records
                if updated_records % 100 == 0:
                    print(f"  Updated {updated_records} records so far...")
        
        processed += len(rows)
        page += 1
        
    print("--------------------------------")
    print(f"Total records processed: {total_records}")
    print(f"Total records updated: {updated_records}")
    print("Done.")
    
except Exception as e:
    print(f"ERROR: An error occurred: {str(e)}")
    sys.exit(1)
finally:
    pass