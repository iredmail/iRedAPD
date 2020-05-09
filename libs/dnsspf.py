import ipaddress
from dns import resolver
from typing import Union

from libs.logger import logger
from libs import utils
import settings


resv = resolver.Resolver()
resv.timeout = settings.DNS_QUERY_TIMEOUT
resv.lifetime = settings.DNS_QUERY_TIMEOUT


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
            qr = resv.query(domain, 'A')
            if qr:
                for r in qr:
                    _ip = str(r)
                    logger.debug(f"[DNS][A] {domain} -> {_ip}")

                    ips.add(_ip)
                    returned_ips.add(_ip)

            queried_domains.add('a:' + domain)
        except (resolver.NoAnswer):
            logger.debug(f"[DNS][A] {domain} -> NoAnswer")
        except resolver.NXDOMAIN:
            logger.debug(f"[DNS][A] {domain} -> NXDOMAIN")
        except (resolver.Timeout):
            logger.info(f"[DNS][A] {domain} -> Timeout")
        except Exception as e:
            logger.debug(f"[DNS][A] {domain} -> Error: {repr(e)}")

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
            qr = resv.query(domain, 'MX')
            if qr:
                for r in qr:
                    hostname = str(r).split()[-1].rstrip('.')
                    logger.debug(f"[SPF][{domain}] MX: {hostname}")
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
        return {
            'spf': None,
            'queried_domains': queried_domains,
        }

    try:
        # WARNING: DO NOT UPDATE queried_domains in this function
        qr = resv.query(domain, 'TXT')
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
    except resolver.NoAnswer:
        pass
    except resolver.NXDOMAIN:
        pass
    except Exception as e:
        logger.debug(f"[SPF] Error while querying DNS SPF record {domain}: {repr(e)}")

    queried_domains.add('spf:' + domain)

    return {
        'spf': spf,
        'queried_domains': queried_domains,
    }


def parse_spf(domain: str,
              spf: Union[str, type(None)],
              queried_domains=None,
              returned_ips=None):
    """Parse value of DNS SPF record."""
    ips = set()
    a = set()
    mx = set()
    included_domains = set()

    queried_domains = queried_domains or set()
    returned_ips = returned_ips or set()

    if not spf:
        return {
            'ips': ips,
            'queried_domains': queried_domains,
            'returned_ips': returned_ips,
        }

    tags = spf.split()

    for tag in tags:
        v = tag.split(':', 1)[-1]

        if tag.startswith('include:') or tag.startswith('+include:'):
            included_domains.add(v)
        elif tag.startswith('redirect='):
            d = tag.split('=', 1)[-1]
            included_domains.add(d)
        elif tag.startswith('ip4:') or tag.startswith('+ip4:'):
            if '/' in v:
                try:
                    ipaddress.ip_network(v)
                    ips.add(v)
                except:
                    logger.debug(f"{tag} is invalid IP address or network.")
            else:
                try:
                    ipaddress.ip_address(v)
                    ips.add(v)
                except:
                    logger.debug(f"{tag} is invalid IP address.")

        elif tag.startswith('ip6:') or tag.startswith('+ip6:'):
            # Some sysadmin uses invalid syntaxes like 'ipv:*', we'd better not
            # store them.
            try:
                ipaddress.ip_address(v)
                ips.add(v)
            except:
                try:
                    ipaddress.ip_network(v)
                    ips.add(v)
                except:
                    logger.debug(f"{tag} is invalid IP address or network.")
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

        logger.debug(f"[SPF][{domain}] 'spf:' tag: {', '.join(included_domains)}")
        qr = query_spf_of_included_domains(included_domains,
                                           queried_domains=queried_domains,
                                           returned_ips=returned_ips)

        ips_included = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_included)

    if a:
        _domains = [i for i in a if 'a:' + i not in queried_domains]

        logger.debug(f"[SPF][{domain}] 'a:' tag: {', '.join(a)}")
        qr = query_a(domains=_domains,
                     queried_domains=queried_domains,
                     returned_ips=returned_ips)

        ips_a = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_a)

    if mx:
        _domains = [i for i in mx if 'mx:' + i not in queried_domains]

        logger.debug(f"[SPF][{domain}] 'mx:' tag: {', '.join(mx)}")
        qr = query_mx(domains=_domains,
                      queried_domains=queried_domains,
                      returned_ips=returned_ips)

        ips_mx = qr['ips']
        queried_domains = qr['queried_domains']
        returned_ips = qr['returned_ips']

        ips.update(ips_mx)

    queried_domains.add('spf:' + domain)

    if ips:
        logger.debug(f"[SPF][{domain}] All IP addresses/networks: {', '.join(ips)}")
    else:
        logger.debug(f"[SPF][{domain}] No valid IP addresses/networks.")

    return {
        'ips': ips,
        'queried_domains': queried_domains,
        'returned_ips': returned_ips,
    }


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
            logger.debug(f"[SPF][include {domain}] {spf}")
        else:
            logger.debug(f"[SPF][include {domain}] empty")

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
    Check whether given IP address is listed in SPF DNS record of given
    sender domain. Return True if exists, False if not.
    """
    if (not sender_domain) or (not ip):
        return False

    qr = query_spf(domain=sender_domain, queried_domains=None)

    _spf = qr['spf']
    queried_domains = qr['queried_domains']

    if not _spf:
        logger.debug(f"[SPF] Domain {sender_domain} does not have a valid SPF DNS record.")
        return False

    qr = parse_spf(domain=sender_domain,
                   spf=_spf,
                   queried_domains=queried_domains)

    _ips = qr['ips']
    if ip in _ips:
        logger.debug(f"[SPF] IP {ip} is listed in SPF DNS record of sender domain {sender_domain}.")
        return True

    _ip_object = ipaddress.ip_address(ip)
    _cidrs = []

    # Get CIDR networks
    if _ip_object.version == 4:
        # if `ip=a.b.c.d`, ip prefix = `a.`
        _ipv4_prefix = ip.split('.', 1)[0] + '.'
        _cidrs = [i for i in _ips if (i.startswith(_ipv4_prefix) and '.0/' in i)]
    elif _ip_object.version == 6:
        _cidrs = [i for i in _ips if (':' in i and '/' in i)]

    if _cidrs:
        for _cidr in _cidrs:
            try:
                _network = ipaddress.ip_network(_cidr)

                if _ip_object in _network:
                    logger.debug(f"[SPF] IP ({ip}) is listed in SPF DNS record "
                                 f"of sender domain {sender_domain} "
                                 f"(network={_cidr}).")
                    return True
            except Exception as e:
                logger.debug(f"[SPF] Error while checking IP {ip} against network {_cidr}: {e}")

    logger.debug(f"[SPF] IP {ip} is NOT listed in SPF DNS record of domain {sender_domain}.")
    return False
