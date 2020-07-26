#!/usr/bin/env python3

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Migrate Cluebringer throttle setting to iRedAPD.

# Usage:
#
#   1) Update cluebringer_db_* parameters below with correct SQL credential.
#
#   2) Run command:
#
#       python3 migrate_cluebringer_throttle.py

cluebringer_db_host = '127.0.0.1'
cluebringer_db_port = 3306
cluebringer_db_name = 'cluebringer'
cluebringer_db_user = 'root'
cluebringer_db_password = ''

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)
import settings
from libs import ACCOUNT_PRIORITIES
from libs.utils import is_email, is_domain
from tools import logger, get_db_conn

backend = settings.backend
if backend in ['pgsql']:
    sql_dbn = 'postgres'
else:
    # backend in ['ldap', 'mysql']
    sql_dbn = 'mysql'

if not (cluebringer_db_host
        and cluebringer_db_port
        and cluebringer_db_name
        and cluebringer_db_user
        and cluebringer_db_password):
    # Not run cluebringer
    sys.exit("Incorrect database info, please update cluebringer_db_* parameters.")

web.config.debug = False
backend = settings.backend

conn = web.database(dbn=sql_dbn,
                    host=cluebringer_db_host,
                    port=int(cluebringer_db_port),
                    db=cluebringer_db_name,
                    user=cluebringer_db_user,
                    pw=cluebringer_db_password)

conn.supports_multiple_insert = True

logger.info("* Backend: {}".format(backend))

# --------------------------
# Get throttle settings.
#

# Construct iRedAPD throttle setting.
t_settings = {}
inbound_settings = {}
outbound_settings = {}

quotas_ids = []

# Get enabled default inbound/outbound throttle.
qr = conn.select(
    'quotas',
    what='id, name, period',
    where=r"""name IN ('default_inbound', 'default_outbound') AND disabled=0""",
)

if qr:
    for rcd in qr:
        _id = rcd.id
        quotas_ids.append(_id)

        _name = rcd.name
        _period = rcd.period

        inout_type = 'outbound'
        if _name == 'default_inbound':
            inout_type = 'inbound'

        t_settings[_id] = {
            'account': '@.',
            'inout_type': inout_type,
            'period': _period,
            'priority': ACCOUNT_PRIORITIES['catchall'],
        }

# Get enabled throttle account and period.
qr = conn.select(
    'quotas',
    what='id, name, period',
    where=r"""(name LIKE 'inbound_%' OR name LIKE 'outbound_%') AND disabled=0""",
)

if qr:
    for rcd in qr:
        _id = rcd.id
        quotas_ids.append(_id)

        _name = rcd.name
        _period = rcd.period

        if _name.startswith('inbound_'):
            _account = _name.split('inbound_', 1)[-1]
            inout_type = 'inbound'
        else:
            _account = _name.split('outbound_', 1)[-1]
            inout_type = 'outbound'

        priority = ACCOUNT_PRIORITIES['catchall']
        if is_email(_account):
            priority = ACCOUNT_PRIORITIES['email']
        elif is_domain(_account):
            _account = '@' + _account
            priority = ACCOUNT_PRIORITIES['domain']

        t_settings[_id] = {
            'account': _account,
            'inout_type': inout_type,
            'period': _period,
            'priority': priority,
        }

if not quotas_ids:
    sys.exit('No throttle settings found. Exit.')

# Get detailed throttle settings.
qr = conn.select(
    'quotas_limits',
    vars={'quotas_ids': quotas_ids},
    what='quotasid, type, counterlimit',
    where='quotasid IN $quotas_ids',
)

if qr:
    for rcd in qr:
        _id = rcd.quotasid
        _type = rcd.type
        _counterlimit = rcd.counterlimit

        if _type == 'MessageCount':
            t_settings[_id]['max_msgs'] = _counterlimit
        elif _type == 'MessageCumulativeSize':
            t_settings[_id]['max_quota'] = _counterlimit

logger.info("Total {} throttle settings.".format(len(t_settings)))

conn = get_db_conn('iredapd')
for t in t_settings:
    v = t_settings[t]
    if not ('max_msgs' in v):
        v['max_msgs'] = -1

    if not ('max_quota' in v):
        v['max_quota'] = -1

    sql = """INSERT INTO throttle (account, kind, priority, period, msg_size, max_msgs, max_quota)
                           VALUES ('%s', '%s', %d, %d, -1, %d, %d)
          """ % (v['account'], v['inout_type'], v['priority'], v['period'], v['max_msgs'], v['max_quota'])

    try:
        conn.query(sql)
    except Exception as e:
        logger.error("<<< Error >>> {}".format(repr(e)))
