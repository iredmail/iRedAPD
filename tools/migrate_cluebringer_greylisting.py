#!/usr/bin/env python

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Migrate Cluebringer greylisting setting to iRedAPD.

# Usage:
#
#   1) Update cluebringer_db_* parameters below with correct SQL credential.
#   2) Run command:

#       # python migrate_cluebringer_throttle.py

cluebringer_db_host = '127.0.0.1'
cluebringer_db_port = 3306
cluebringer_db_name = 'cluebringer'
cluebringer_db_user = 'cluebringer'
cluebringer_db_password = '3aUBn3OBYUgJ2Ddbmwyh8OHQ3Dcz50'

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)
import settings
from libs import ACCOUNT_PRIORITIES
from libs.utils import is_email, is_domain
from tools import debug, logger, get_db_conn

backend = settings.backend
if backend in ['ldap', 'mysql']:
    sql_dbn = 'mysql'
elif backend in ['pgsql']:
    sql_dbn = 'postgres'

if not (cluebringer_db_host \
        and cluebringer_db_port \
        and cluebringer_db_name \
        and cluebringer_db_user \
        and cluebringer_db_password):
    # Not run cluebringer
    sys.exit("Incorrect database info, please update cluebringer_db_* parameters.")

web.config.debug = debug
backend = settings.backend
conn_iredapd = get_db_conn('iredapd')

conn_cb = web.database(dbn=sql_dbn,
                       host=cluebringer_db_host,
                       port=int(cluebringer_db_port),
                       db=cluebringer_db_name,
                       user=cluebringer_db_user,
                       pw=cluebringer_db_password)

conn_cb.supports_multiple_insert = True

logger.info('* Backend: %s' % backend)

# Get enabled GLOBAL/SERVER-WIDE greylisting setting.
qr = conn_cb.select('greylisting',
                    what='id',
                    where="name='Greylisting Inbound Emails'",
                    limit=1)

if qr:
    id_default = qr[0].id
    # TODO Migrate default greylisting setting

# Migrate whitelists
qr = conn_cb.select('greylisting_whitelist',
                    what='id, source, comment',
                    where='disabled=0')

for rcd in qr:
    if rcd.source.startswith('SenderIP:'):
        wl = rcd.source.split('SenderIP:', 1)[-1]

        comment = ''
        if rcd.comment:
            comment = rcd.comment.title()

        sql = """INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '%s', '%s');""" % (wl, comment)
        try:
            conn_iredapd.execute(sql)
        except Exception, e:
            pass
