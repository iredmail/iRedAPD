from dns import resolver

from libs.logger import logger
from libs import utils, ipaddress


def query_a(domains, queried_domains=None, returned_ips=None):
    """
    Return a list of IP addresses/networks defined in A record of mail domain
    names.

    @domains - a list/tuple/set of mail domain names
    @queried_domains - a set of mail domain names which already queried spf
    @returned_ips - a set of IP addr/networks of queried mail domain names
    """
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
                    logger.debug('[SPF][%s] A: %s' % (domain, _ip))

                    ips.add(_ip)
                    returned_ips.add(_ip)

            queried_domains.add('a:' + domain)
        except Exception, e:
            logger.debug('[SPF]Error while querying DNS A record %s: %s' % (domain, repr(e)))

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


def query_mx(domains, queried_domains=None, returned_ips=None):
    """
    Return a list of IP addresses/networks defined in MX record of mail domain
    names.

    @domains - a list/tuple/set of mail domain names
    @queried_domains - a set of mail domain names which already queried spf
    @returned_ips - a set of IP addr/networks of queried mail domain names
    """
    ips = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    hostnames = set()

    domains = [d for d in domains if d not in queried_domains]
    for domain in domains:
        try:
            qr = resolver.query(domain, 'MX')
            if qr:
                for r in qr:
                    hostname = str(r).split()[-1].rstrip('.')
                    logger.debug('[SPF][%s] MX: %s' % (domain, hostname))
                    if utils.is_domain(hostname):
                        hostnames.add(hostname)

            if hostnames:
                qr = query_a(domains=hostnames,
                             queried_domains=queried_domains,
                             returned_ips=returned_ips)

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
    """Return SPF record of given domain name."""
    spf = None

    queried_domains = queried_domains or set()
    if 'spf:' + domain in queried_domains:
        return {'spf': None,
                'queried_domains': queried_domains}

    try:
        # WARNING: DO NOT UPDATE queried_domains in this function
        qr = resolver.query(domain, 'TXT')
        for r in qr:
            # Remove heading/ending quotes
            r = str(r).strip('"').strip("'")

            # Some SPF records contains splited IP address like below:
            #   v=spf1 ... ip4:66.220.157" ".0/25 ...
            # We should remove '"' and combine them.
            _v = [v for v in r.split('"') if not v.startswith(' ')]
            r = ''.join(_v)

            if r.startswith('v=spf1'):
                spf = r
                break
    except Exception, e:
        logger.debug('[SPF] Error while querying DNS SPF record %s: %s' % (domain, repr(e)))

    queried_domains.add('spf:' + domain)

    return {'spf': spf,
            'queried_domains': queried_domains}


def parse_spf(domain, spf, queried_domains=None, returned_ips=None):
    """Parse value of DNS SPF record."""
    ips = set()
    a = set()
    mx = set()
    included_domains = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    if not spf:
        return {'ips': ips,
                'queried_domains': queried_domains,
                'returned_ips': returned_ips}

    tags = spf.split()

    for tag in tags:
        v = tag.split(':', 1)[-1]

        if tag.startswith('include:'):
            included_domains.add(v)
        elif tag.startswith('redirect='):
            d = tag.split('=', 1)[-1]
            included_domains.add(d)
        elif tag.startswith('ip4:') or tag.startswith('+ip4:'):
            if '.0/' in v:
                try:
                    ipaddress.ip_network(unicode(v))
                    ips.add(v)
                except:
                    logger.debug("%s is invalid ip address or network." % tag)
            elif '/' in v:
                v = v.split('/', 1)[0]
                try:
                    ipaddress.ip_address(unicode(v))
                    ips.add(v)
                except:
                    logger.debug("%s is invalid ip address or network." % tag)
            else:
                ips.add(v)

        elif tag.startswith('ip6:') or tag.startswith('+ip6:'):
            # Some sysadmin uses invalid syntaxes like 'ipv:*', we'd better not
            # store them.
            try:
                ipaddress.ip_address(unicode(v))
                ips.add(v)
            except:
                try:
                    ipaddress.ip_network(unicode(v))
                    ips.add(v)
                except:
                    logger.debug("%s is invalid ip address or network." % tag)
        elif tag.startswith('a:') or tag.startswith('+a:'):
            a.add(v)
        elif tag.startswith('mx:') or tag.startswith('+mx:'):
            mx.add(v)
        elif tag.startswith('ptr:'):
            ips.add('@' + v)
        elif tag == 'a' or tag == '+a':
            a.add(domain)
        elif tag == 'mx' or tag == '+mx':
            mx.add(domain)
        elif tag == 'ptr':
            ips.add('@' + domain)

    # Find IP in included_domains
    if included_domains:
        included_domains = [i for i in included_domains if 'spf:' + i not in queried_domains]

        logger.debug("[SPF][%s] 'spf:' tag: %s" % (domain, ', '.join(included_domains)))
        qr = query_spf_of_included_domains(included_domains,
                                           queried_domains=queried_domains,
                                           returned_ips=returned_ips)

        ips_included = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_included)

    if a:
        _domains = [i for i in a if 'a:' + i not in queried_domains]

        logger.debug("[SPF][%s] 'a:' tag: %s" % (domain, ', '.join(a)))
        qr = query_a(domains=_domains,
                     queried_domains=queried_domains,
                     returned_ips=returned_ips)

        ips_a = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_a)

    if mx:
        _domains = [i for i in mx if 'mx:' + i not in queried_domains]

        logger.debug("[SPF][%s] 'mx:' tag: %s" % (domain, ', '.join(mx)))
        qr = query_mx(domains=_domains,
                      queried_domains=queried_domains,
                      returned_ips=returned_ips)

        ips_mx = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_mx)

    queried_domains.add('spf:' + domain)

    if ips:
        logger.debug("[SPF][%s] All IP addresses/networks: %s" % (domain, ', '.join(ips)))
    else:
        logger.debug("[SPF][%s] No valid IP addresses/networks." % domain)

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


def query_spf_of_included_domains(domains,
                                  queried_domains=None,
                                  returned_ips=None):
    """
    Return a set of IP addresses/networks defined in SPF record of given mail
    domain names.
    """
    ips = set()
    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    domains = [d for d in domains if 'spf:' + d not in queried_domains]
    for domain in domains:
        qr = query_spf(domain=domain, queried_domains=queried_domains)
        spf = qr['spf']
        queried_domains = qr['queried_domains']

        if spf:
            logger.debug('[SPF][include %s] %s' % (domain, spf))
        else:
            logger.debug('[SPF][include %s] empty' % domain)

        qr = parse_spf(domain=domain,
                       spf=spf,
                       queried_domains=queried_domains,
                       returned_ips=returned_ips)

        ips_spf = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_spf)
        queried_domains.add('spf:' + domain)
        returned_ips.update(ips_spf)

    return {'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips}


def is_allowed_server_in_spf(sender_domain, ip):
    """
    Return True|False if given IP address is one of allowed servers defined
    in DNS SPF record.
    """
    qr = query_spf(domain=sender_domain, queried_domains=None)

    _spf = qr['spf']
    queried_domains = qr['queried_domains']

    if not _spf:
        logger.info('[SPF] Domain %s does not have an valid DNS SPF record, client %s is treated as disallowed server.' % (sender_domain, ip))
        return False

    qr = parse_spf(domain=sender_domain,
                   spf=_spf,
                   queried_domains=queried_domains)

    _ips = qr['ips']
    if ip in _ips:
        logger.info('[SPF] IP %s is explicitly listed in DNS SPF record of domain %s.' % (ip, sender_domain))
        return True

    _ip_object = ipaddress.ip_address(unicode(ip))
    _cidrs = []

    # Get CIDR networks
    if _ip_object.version == 4:
        # if `ip=a.b.c.d`, ip prefix = `a.b.`
        _ipv4_prefix = '.'.join(ip.split('.', 2)[:2]) + '.'
        _cidrs = [i for i in _ips if (i.startswith(_ipv4_prefix) and '.0/' in i)]
    elif _ip_object.version == 6:
        _cidrs = [i for i in _ips if (':' in i and '/' in i)]

    if _cidrs:
        for _cidr in _cidrs:
            try:
                _network = ipaddress.ip_network(unicode(_cidr))

                if _ip_object in _network:
                    logger.info('[SPF] IP (%s) is in IP network (%s) listed in DNS SPF record of domain %s.' % (ip, _cidr, sender_domain))
                    return True
            except Exception, e:
                logger.debug('[SPF] Error while checking IP %s with network %s: %s' % (ip, _cidr, repr(e)))

    logger.info('[SPF] IP %s is NOT listed in DNS SPF record of domain %s, treated as disallowed server.' % (ip, sender_domain))
    return False
