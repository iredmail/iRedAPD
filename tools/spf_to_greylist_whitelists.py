#!/usr/bin/env python

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Query SPF DNS record of specified domains and import returned IP
#          addresses/networks in to iRedAPD database as greylisting whitelists.

#
# USAGE
#
#   You can run this script with or without arguments.
#
#   1) Run this script without any arguments:
#
#       $ python spf_to_greylist_whitelists.py
#
#      It will query SQL table `iredapd.greylisting_whitelist_domains` to get
#      the mail domain names.
#
#   2) Run this script with mail domain names which you want to disable
#      gryelisting:
#
#       $ python spf_to_greylist_whitelists.py <domain> [domain ...]
#
#      For example:
#
#       $ python spf_to_greylist_whitelists.py google.com aol.com
#
#   3) Run this script with option '--submit' and domain name to add domain
#      name to SQL table `iredapd.greylisting_whitelist_domains`, and query
#      its SPF/MX/A records immediately, and remove all greylisting tracking
#      data (since it's whitelisted, we don't need the tracking data anymore):
#
#       $ python spf_to_greylist_whitelists.py --submit <domain> [domain ...]
#
# Required third-party Python modules:
#
#   - dnspython: https://pypi.python.org/pypi/dnspython
#   - web.py: http://webpy.org/

#
# KNOWN ISSUES
#
#   * not supported spf syntax:
#
#       - -all
#       - a/24 a:<domain>/24
#       - mx/24 mx:<domain>/24
#       - exists:<domain>

#
# REFERENCES
#
#   * SPF Record Syntax: http://www.openspf.org/SPF_Record_Syntax
#   * A simpler shell script which does the same job, it lists all IP addresses
#     and/or networks on terminal: https://bitbucket.org/zhb/spf-to-ip

import os
import sys
import logging
import web
web.config.debug = False

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from tools import logger, get_db_conn
from libs import utils, dnsspf

if '--debug' in sys.argv:
    logger.setLevel(logging.DEBUG)
    sys.argv.remove('--debug')
else:
    logger.setLevel(logging.INFO)

# Add domain name to SQL table `iredapd.greylisting_whitelist_domains`
submit_to_sql_db = False
if '--submit' in sys.argv:
    submit_to_sql_db = True
    sys.argv.remove('--submit')


conn = get_db_conn('iredapd')

if len(sys.argv) == 1:
    logger.info('* Query SQL server to get mail domain names.')

    domains = []

    qr = conn.select('greylisting_whitelist_domains', what='domain')
    for r in qr:
        domains.append(r.domain)
else:
    domains = sys.argv[1:]

domains = [str(d).lower() for d in domains if utils.is_domain(d)]
if not domains:
    logger.info('* No valid domain names. Abort.')
    sys.exit()

logger.info('* %d mail domains in total.' % len(domains))

all_ips = set()
domain_ips = {}
queried_domains = set()
returned_ips = set()

for domain in domains:
    if 'spf:' + domain in queried_domains:
        continue

    logger.info('\t+ [%s]' % domain)

    # Query SPF record
    qr = dnsspf.query_spf(domain, queried_domains=queried_domains)
    spf = qr['spf']
    queried_domains = qr['queried_domains']

    if spf:
        logger.debug('\t\t+ SPF -> %s' % spf)

        # Parse returned SPF record
        qr = dnsspf.parse_spf(domain, spf, queried_domains=queried_domains, returned_ips=returned_ips)
    else:
        # Whitelist hosts listed in MX records.
        qr = dnsspf.query_mx([domain], queried_domains=queried_domains, returned_ips=returned_ips)

    ips = qr['ips']
    queried_domains = qr['queried_domains']
    returned_ips = qr['returned_ips']

    domain_ips[domain] = ips
    all_ips.update(ips)

    logger.debug('\t\t+ Result: %s' % ips)

if not all_ips:
    logger.info('* No IP address/network found. Exit.')
    sys.exit()

# Import IP addresses/networks as greylisting whitelists.
for domain in domain_ips:
    comment = 'AUTO-UPDATE: %s' % domain
    sql_vars = {'domain': domain,
                'account': '@.',
                'comment': comment}

    # Delete old records
    try:
        conn.delete('greylisting_whitelist_domain_spf',
                    vars=sql_vars,
                    where="comment=$comment")

        # in iRedAPD-2.0 and earlier releases, results were stored in
        # sql table `greylisting_whitelists`
        conn.delete('greylisting_whitelists',
                    vars=sql_vars,
                    where="comment=$comment")
    except Exception as e:
        logger.info('* <<< ERROR >>> Cannot delete old record for domain %s: %s' % (domain, str(e)))

    # Insert new records
    for ip in domain_ips[domain]:
        try:
            # Check whether we already have this sender. used to avoid annoying
            # warning message in PostgreSQL log file due to duplicate key.
            qr = conn.select('greylisting_whitelist_domain_spf',
                             vars={'account': '@.', 'sender': ip},
                             what='id',
                             where='account=$account AND sender=$sender',
                             limit=1)

            if not qr:
                # Insert new whitelist
                conn.insert('greylisting_whitelist_domain_spf',
                            account='@.',
                            sender=ip,
                            comment=comment)

                # Clean up `greylisting_tracking` table
                conn.delete('greylisting_tracking',
                            vars={'ip': ip},
                            where='client_address=$ip')

        except Exception as e:
            if e.__class__.__name__ == 'IntegrityError':
                pass
            else:
                logger.error('* <<< ERROR >>> Cannot insert new record for domain %s: %s' % (domain, e.message))

if submit_to_sql_db:
    logger.info('* Store domain names in SQL database as greylisting whitelists.')
    for d in domains:
        try:
            conn.insert('greylisting_whitelist_domains', domain=d)
        except Exception as e:
            logger.error('<<< ERROR >>> %s' % str(e))
