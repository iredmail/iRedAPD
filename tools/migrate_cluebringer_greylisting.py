#!/usr/bin/env python

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Migrate Cluebringer greylisting setting to iRedAPD.

# Usage:
#
#   1) Update cluebringer_db_* parameters below with correct SQL credential.
#   2) Run command:

#       # python migrate_cluebringer_throttle.py

cluebringer_db_host = '127.0.0.1'
cluebringer_db_port = 5432
cluebringer_db_name = 'cluebringer'
cluebringer_db_user = 'cluebringer'
cluebringer_db_password = '0T2JIsDuX7yHWAakgIcSJt2i6LZk2I'

import os
import sys
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)
import settings
from libs import ACCOUNT_PRIORITIES
from libs.utils import is_valid_amavisd_address
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

#
# Global greylisting setting
#
logger.info('* Migrate global greylisting setting.')
logger.info('\t- Query enabled global greylisting setting.')
qr = conn_cb.select('greylisting',
                    what='id',
                    where="name='Greylisting Inbound Emails' AND usegreylisting=1",
                    limit=1)

if qr:
    logger.info('\t- Cluebringer has greylisting enabled globally.')
    # Check existing global greylisting setting
    qr = conn_iredapd.select('greylisting',
                             what='id',
                             where="account='@.' AND sender='@.'",
                             limit=1)

    if qr:
        logger.info('\t- iRedAPD already has global greylisting setting, not migrate Cluebringer global setting.')
    else:
        logger.info("\t- iRedAPD doesn't have global greylisting setting, migrating ...")
        conn_iredapd.insert('greylisting',
                            account='@.',
                            priority=0,
                            sender='@.',
                            sender_priority=0,
                            active=1)

#
# no_greylisting settings
#
logger.info('* Migrate per-domain and per-user no-greylisting settings.')

logger.info('\t- Query no-greylisting settings')
qr = conn_cb.select(['policy_groups', 'policy_group_members'],
                    what='policy_group_members.member AS member',
                    where="policy_groups.name='no_greylisting_for_internal' AND policy_group_members.policygroupid=policy_groups.id")

for r in qr:
    _account = str(r.member)
    _account_type = is_valid_amavisd_address(_account)
    if _account_type:
        _priority = ACCOUNT_PRIORITIES[_account_type]
    else:
        continue

    try:
        conn_iredapd.insert('greylisting',
                            account=r.member,
                            priority=_priority,
                            sender='@.',
                            sender_priority=0,
                            active=1)
        logger.info('\t+ Migrated account setting: %s' % _account)
    except Exception, e:
        logger.info('\t+ Failed migrating account setting: %s' % _account)

#
# Greylisting whitelists
#
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
