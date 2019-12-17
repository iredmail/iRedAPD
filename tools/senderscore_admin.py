#!/usr/bin/env python2

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Manage senderscore data.

from __future__ import print_function
import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

#import settings
#from tools import logger, get_db_conn, sql_count_id
from tools import logger, get_db_conn
from libs import utils

web.config.debug = False

# `4102444799` seconds since 1970-01-01 is '2099-12-31 23:59:59'.
# It's a trick to use this time as whitelist and not cleaned by
# script `tools/cleanup_db.py`.
# It's ok to use any long epoch seconds to avoid cleanup, but we use this
# hard-coded value for easier management.
expire_epoch_seconds = 4102444799

USAGE = """Usage:

    -w Whitelist given IP address(es).
       Multiple IP addresses must be separated by whitespace.

"""

if len(sys.argv) <= 2:
    print(USAGE)
    sys.exit()


args = [v for v in sys.argv[1:]]
ips = []
action = None

if '-w' in args:
    action = 'whitelist'
    ips = [i for i in args[1:] if utils.is_strict_ip(i)]
    if not ips:
        print("No valid IP address.")
        print(USAGE)
        sys.exit()
else:
    print("Invalid argument.\n\n")
    print(USAGE)
    sys.exit()


conn = get_db_conn('iredapd')

if action == 'whitelist':
    # Remove existing records first.
    conn.delete("senderscore_cache",
                vars={'ips': ips},
                where="client_address IN $ips")

    rows = []
    for ip in ips:
        rows += [{'client_address': ip,
                  'score': 100,
                  'time': expire_epoch_seconds}]

    # Insert whitelist.
    conn.multiple_insert("senderscore_cache", rows)
    logger.info("Whitelisted: {0}".format(", ".join(ips)))
