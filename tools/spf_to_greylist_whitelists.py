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
# Required third-party Python modules:
#
#   - dnspython
#   - web.py

#
# KNOWN ISSUES
#
#   * not supported spf syntax:
#
#       - ptr ptr:<domain>
#       - a/24 a:<domain>/24
#       - mx/24 mx:<domain>/24
#       - exists:<domain>

#
# REFERENCES
#
#   * SPF Record Syntax: http://www.openspf.org/SPF_Record_Syntax
#   * A simpler shell script which does the same job, it lists all IP addresses
#     and/or networks on terminal: https://bitbucket.org/zhb/spf-to-ip

#
# TODO
#
#   - support spf syntax: ptr ptr:<domain>
#   - import generated SQL file directly.

import os
import sys
import web

try:
    from dns import resolver
except ImportError:
    print "<<< ERROR >>> Please install Python module 'dnspython' first."

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from tools import logger, get_db_conn
from libs import utils


def query_a(domains, queried_domains=None, returned_ips=None):
    "Return list of IP addresses/networks defined in A record of domain name."
    ips = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    domains = [d for d in domains if d not in queried_domains]
    for domain in domains:
        try:
            qr = resolver.query(domain, 'A')
            if qr:
                for r in qr:
                    _ip = str(r)
                    ips.add(_ip)

                    returned_ips.add(_ip)

            queried_domains.add('a:' + domain)
        except:
            pass

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


def query_mx(domains, queried_domains=None, returned_ips=None):
    "Return list of IP addresses/networks defined in MX record of domain name."
    ips = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    a = set()

    domains = [d for d in domains if d not in queried_domains]
    for domain in domains:
        try:
            qr = resolver.query(domain, 'MX')
            if qr:
                for r in qr:
                    hostname = str(r).split()[-1].rstrip('.')
                    a.add(hostname)

            if a:
                qr = query_a(a, queried_domains=queried_domains, returned_ips=returned_ips)

                ips_a = qr['ips']
                queried_domains = qr['queried_domains']
                returned_ips = qr['returned_ips']

                ips.update(ips_a)

            queried_domains.add('mx:' + domain)
        except:
            pass

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


def query_spf(domain, queried_domains=None):
    """Return spf record of given domain."""
    spf = None

    queried_domains = queried_domains or set()
    if 'spf:' + domain in queried_domains:
        return {'spf': None,
                'queried_domains': queried_domains}

    # WARNING: DO NOT UPDATE queried_domains in this function
    try:
        qr = resolver.query(domain, 'TXT')
        for r in qr:
            # Remove heading/ending quotes
            r = str(r).strip('"').strip("'")

            if r.startswith('v=spf1'):
                spf = r
                break
    except:
        pass

    return {'spf': spf,
            'queried_domains': queried_domains}


def query_spf_of_included_domains(domains, queried_domains=None, returned_ips=None):
    """Return set of IP addresses and/or networks defined in SPF record of
    given mail domain names."""
    ips = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    domains = [d for d in domains if 'spf:' + d not in queried_domains]
    for domain in domains:
        qr = query_spf(domain, queried_domains=queried_domains)
        spf = qr['spf']
        queried_domains = qr['queried_domains']

        qr = parse_spf(domain, spf, queried_domains=queried_domains, returned_ips=returned_ips)

        ips_spf = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_spf)

        queried_domains.add('spf:' + domain)
        returned_ips.update(ips_spf)

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


def parse_spf(domain, spf, queried_domains=None, returned_ips=None):
    """Parse spf record."""
    ips = set()
    a = set()
    mx = set()
    included_domains = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    if 'spf:' + domain in queried_domains:
        logger.debug('\t- [SKIP] %s had been queried.' % domain)
        return {'ips': ips,
                'queried_domains': queried_domains,
                'returned_ips': returned_ips}

    if not spf:
        return ips

    tags = spf.split()

    for tag in tags:
        v = tag.split(':', 1)[-1]

        if tag.startswith('include:'):
            included_domains.add(v)
        elif tag.startswith('redirect='):
            d = tag.split('=', 1)[-1]
            included_domains.add(d)
        elif tag.startswith('ip4:') or tag.startswith('ip6:'):
            ips.add(v)
        elif tag.startswith('a:'):
            a.add(v)
        elif tag.startswith('mx:'):
            mx.add(v)
        elif tag.startswith('ptr:'):
            ips.add('@' + v)
        elif tag == 'a':
            a.add(domain)
        elif tag == 'mx':
            mx.add(domain)

    # Find IP in included_domains
    if included_domains:
        included_domains = [i for i in included_domains if 'spf:' + i not in queried_domains]

        logger.debug('\t+ [%s] include: -> %s' % (domain, ', '.join(included_domains)))
        qr = query_spf_of_included_domains(included_domains,
                                           queried_domains=queried_domains,
                                           returned_ips=returned_ips)

        ips_included = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_included)

    if a:
        a = [i for i in a if 'a:' + i not in queried_domains]

        logger.debug('\t+ [%s] A -> %s' % (domain, ', '.join(a)))
        qr = query_a(a, queried_domains=queried_domains, returned_ips=returned_ips)

        ips_a = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_a)

    if mx:
        mx = [i for i in mx if 'mx:' + i not in queried_domains]

        logger.debug('\t+ [%s] MX -> %s' % (domain, ', '.join(mx)))
        qr = query_mx(mx, queried_domains=queried_domains, returned_ips=returned_ips)

        ips_mx = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_mx)

    queried_domains.add('spf:' + domain)

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


web.config.debug = False
conn = get_db_conn('iredapd')

if len(sys.argv) == 1:
    logger.error('* Query SQL server to get mail domain names.')

    domains = []

    qr = conn.select('greylisting_whitelist_domains',
                     what='domain')
    for r in qr:
        domains.append(r.domain)
else:
    domains = sys.argv[1:]

domains = [d for d in domains if utils.is_domain(d)]
if not domains:
    logger.info('* No valid domain names, exit.')

logger.info('* Parsing domains, %d in total.' % len(domains))

all_ips = set()
domain_ips = {}
queried_domains = set()
returned_ips = set()

for domain in domains:
    # Convert domain name to lower cases.
    domain = domain.lower()

    if 'spf:' + domain in queried_domains:
        continue

    # Query SPF record
    qr = query_spf(domain, queried_domains=queried_domains)
    spf = qr['spf']
    queried_domains = qr['queried_domains']

    if not spf:
        # TODO whitelist mx records
        continue

    logger.info('\t+ [%s] SPF -> %s' % (domain, spf))

    # Parse returned SPF record
    qr = parse_spf(domain, spf, queried_domains=queried_domains, returned_ips=returned_ips)

    ips = qr['ips']
    queried_domains = qr['queried_domains']
    returned_ips = qr['returned_ips']

    domain_ips[domain] = ips
    all_ips.update(ips)

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
        conn.delete('greylisting_whitelists',
                    vars=sql_vars,
                    where="comment=$comment")
    except Exception, e:
        logger.info('* <<< ERROR >>> Cannot delete old record for domain %s: %s' % (domain, str(e)))

    # Insert new records
    for ip in domain_ips[domain]:
        try:
            conn.insert('greylisting_whitelists',
                        account='@.',
                        sender=ip,
                        comment=comment)
        except Exception, e:
            error = str(e).lower()
            if 'duplicate key' in error or 'duplicate entry' in error:
                pass
            else:
                logger.info('* <<< ERROR >>> Cannot insert new record for domain %s: %s' % (domain, error))
