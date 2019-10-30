# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Lookup server reputation against senderscore.com.
#          If the reputation score returned by DNS query equals to or is lower
#          than reject score (defaults to 30), email will be rejected.

import time
from dns import resolver
from web import sqlquote

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

    score = 100
    cache_the_score = False
    cache_matched = False
    conn_iredapd = kwargs['conn_iredapd']

    # Check cached score from SQL db to speed it up.
    #
    # - Sometimes DNS query might be an issue due to slow reply or temporary
    #   network issue, caching the result will help avoid similar issue.
    # - SQL query is faster than DNS query, especially when server doesn't run
    #   a local DNS server.
    # - It's normal that same sender server sends few emails in short period.
    # - Cached results will be cleaned up automatically by cron job
    #  (tools/cleanup_db.py).

    sql = """
        SELECT score
        FROM senderscore_cache
        WHERE client_address=%s
        LIMIT 1
        """ % sqlquote(client_address)

    qr = conn_iredapd.execute(sql)
    row = qr.fetchone()

    if row:
        try:
            score = int(row[0])
            cache_matched = True
        except Exception as e:
            logger.error("[{0}] senderscore -> Error while converting score "
                         "to integer: {1}".format(client_address, e))
    else:
        (o1, o2, o3, o4) = client_address.split(".")
        lookup_domain = "{0}.{1}.{2}.{3}.score.senderscore.com".format(o4, o3, o2, o1)

        try:
            qr = resv.query(lookup_domain, "A")
            if not qr:
                return SMTP_ACTIONS["default"]

            ip = str(qr[0])
            score = int(ip.split(".")[-1])
            cache_the_score = True
        except (resolver.NoAnswer):
            logger.debug("[{0}] senderscore -> NoAnswer".format(client_address))
            cache_the_score = True
        except resolver.NXDOMAIN:
            logger.debug("[{0}] senderscore -> NXDOMAIN".format(client_address))
            cache_the_score = True
        except (resolver.Timeout):
            logger.debug("[{0}] senderscore -> Timeout".format(client_address))
        except Exception as e:
            logger.error("[{0}] senderscore -> Error: {1}".format(client_address, e))

    if score >= 0 and score <= 100:
        if cache_the_score:
            # Store the DNS query result as cache.
            sql = """
                    INSERT INTO senderscore_cache (client_address, score, time)
                    VALUES (%s, %s, %d)
                """ % (sqlquote(client_address), sqlquote(score), int(time.time()))

            try:
                conn_iredapd.execute(sql)
            except Exception as e:
                logger.error("[{0}] senderscore -> Error while caching score: {1}".format(client_address, e))
    else:
        logger.error("Invalid sender score: %d (must between 0-100)" % score)
        return SMTP_ACTIONS['default']

    sender_domain = kwargs["sasl_username_domain"] or kwargs["sender_domain"]

    log_msg = "[{0}] [{1}] senderscore: {2}".format(client_address, sender_domain, score)
    if cache_matched:
        log_msg += " (cache matched)"

    if score <= reject_score:
        log_msg += " [REJECT (<= {0})]".format(reject_score)
        logger.info(log_msg)
        return SMTP_ACTIONS["reject_low_sender_score"]

    logger.info(log_msg)
    return SMTP_ACTIONS["default"]
