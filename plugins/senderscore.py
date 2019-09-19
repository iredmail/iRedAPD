# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Lookup server reputation against senderscore.com.
#          If the reputation score returned by DNS query equals to or is lower
#          than reject score (defaults to 30), email will be rejected.

from dns import resolver
from libs.logger import logger
from libs import SMTP_ACTIONS
from libs import utils

import settings

resv = resolver.Resolver()
resv.timeout = settings.DNS_QUERY_TIMEOUT
resv.lifetime = settings.DNS_QUERY_TIMEOUT

reject_score = settings.SENDERSCORE_REJECT_SCORE


def restriction(**kwargs):
    # Bypass outgoing emails.
    if kwargs['sasl_username']:
        logger.debug('Found SASL username, bypass senderscore checking.')
        return SMTP_ACTIONS['default']

    client_address = kwargs["client_address"]
    if not utils.is_ipv4(client_address):
        logger.debug('Client address is not IPv4, bypass senderscore checking.')
        return SMTP_ACTIONS["default"]

    if utils.is_trusted_client(client_address):
        logger.debug('Client address is trusted, bypass senderscore checking.')
        return SMTP_ACTIONS['default']

    (o1, o2, o3, o4) = client_address.split(".")
    lookup_domain = "{0}.{1}.{2}.{3}.score.senderscore.com".format(o4, o3, o2, o1)

    score = 100
    try:
        qr = resv.query(lookup_domain, "A")
        ip = str(qr[0])
        score = int(ip.split(".")[-1])
        if not qr:
            return SMTP_ACTIONS["default"]
    except (resolver.NoAnswer):
        logger.debug("[{0}] senderscore -> NoAnswer".format(client_address))
    except resolver.NXDOMAIN:
        logger.debug("[{0}] senderscore -> NXDOMAIN".format(client_address))
    except (resolver.Timeout):
        logger.info("[{0}] senderscore -> Timeout".format(client_address))
    except Exception as e:
        logger.debug("[{0}] senderscore -> Error: {1}".format(client_address, e))

    sender_domain = kwargs["sasl_username_domain"] or kwargs["sender_domain"]

    log_msg = "[{0}] [{1}] senderscore: {2}".format(
        client_address, sender_domain, score
    )
    if score <= reject_score:
        log_msg += " [REJECT (<= {0})]".format(reject_score)
        logger.info(log_msg)
        return SMTP_ACTIONS["reject_low_sender_score"]

    logger.info(log_msg)

    return SMTP_ACTIONS["default"]
