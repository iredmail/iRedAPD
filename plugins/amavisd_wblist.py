# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Reject senders listed in per-user blacklists, bypass senders listed
#          in per-user whitelists stored in Amavisd database (@lookup_sql_dsn).
#
# Note: Amavisd is configured to be an after-queue content filter in iRedMail.
#       with '@lookup_sql_dsn' setting enabled in Amavisd config file, Amavisd
#       will query per-recipient, per-domain and server-wide (a.k.a. catch-all)
#       white/blacklists and policy rules (tables: `mailaddr`, `users`,
#       `wblist`, `policy`) stored in Amavisd SQL database.
#
#       if you don't enable this plugin, Amavisd will quarantine emails sent
#       from blacklisted senders, and bypass spam scanning for emails sent from
#       whitelisted senders (note: other checkings like banned filename, bad
#       headers, virus are still checked - if you didn't disable them in
#       `amavisd.policy`). With this plugin, we can tell Postfix to reject
#       blacklisted sender BEFORE email enter mail queue, or bypass emails sent
#       from whitelisted senders directly.
#
# How to use this plugin:
#
#   *) Enable `@lookup_sql_dsn` with correct SQL account credential in Amavisd
#      config file.
#
#   *) Set Amavisd lookup SQL database related parameters (`amavisd_db_*`) in
#      iRedAPD config file `/opt/iredapd/settings.py`.
#
#   *) Enable this plugin in iRedAPD config file `/opt/iredapd/settings.py`,
#      parameter `plugins =`.
#
#   *) Restart iRedAPD service.
#
# Formats of valid white/blacklist senders:
#
#   - user@domain.com:  single sender email address
#   - @domain.com:  entire sender domain
#   - @.domain.com: entire sender domain and all sub-domains
#   - @.:           all senders
#   - 192.168.1.2: single sender ip address
#   - 192.168.1.0/24: CIDR network.
#   - 192.168.1.*, 192.168.*.2: wildcard sender ip addresses. [DEPRECATED]
#                   NOTE: if you want to use wildcard IP address like
#                   '192.*.1.2', '192.*.*.2', please set
#                   'WBLIST_ENABLE_ALL_WILDCARD_IP = True' in
#                   /opt/iredapd/settings.py.

import ipaddress
from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS
from libs.utils import is_ipv4, wildcard_ipv4, get_policy_addresses_from_email
import settings

SMTP_PROTOCOL_STATE = ["RCPT"]
REQUIRE_AMAVISD_DB = True

if settings.backend == "ldap":
    from libs.ldaplib.conn_utils import is_local_domain, get_alias_target_domain
else:
    from libs.sql import is_local_domain, get_alias_target_domain


if settings.WBLIST_DISCARD_INSTEAD_OF_REJECT:
    reject_action = SMTP_ACTIONS["discard"]
else:
    reject_action = SMTP_ACTIONS["reject_blacklisted"]


def get_id_of_possible_cidr_network(conn, client_address):
    """Return list of `mailaddr.id` which are CIDR network addresses."""
    ids = []

    if not client_address:
        logger.debug("No client address.")
        return ids

    try:
        _ip = ipaddress.ip_address(client_address)
        if _ip.version == 4:
            first_field = client_address.split(".")[0]
            sql_cidr = first_field + r".%%"
        else:
            return ids
    except:
        return ids

    sql = f"""SELECT id, email
               FROM mailaddr
              WHERE email LIKE {sqlquote(sql_cidr)}
           ORDER BY priority DESC"""
    logger.debug(f"[SQL] Query CIDR network: \n{sql}")

    try:
        qr = conn.execute(sql)
        qr_cidr = qr.fetchall()
    except Exception as e:
        logger.error(f"Error while querying CIDR network: {repr(e)}, SQL: \n{sql}")
        return ids

    if qr_cidr:
        _cidrs = [(int(r.id), r.email.decode()) for r in qr_cidr]

        # Get valid CIDR.
        _ip_networks = set()
        for (_id, _cidr) in _cidrs:
            # Verify whether client_address is in CIDR network
            try:
                _net = ipaddress.ip_network(_cidr)
                _ip_networks.add((_id, _net))
            except:
                pass

        if _ip_networks:
            _ip = ipaddress.ip_address(client_address)
            for (_id, _net) in _ip_networks:
                if _ip in _net:
                    ids.append(_id)

    logger.debug(f"IDs of CIDR network(s): {ids}")
    return ids


def get_id_of_external_addresses(conn, addresses):
    """Return list of `mailaddr.id` of external addresses."""
    ids = []

    if not addresses:
        logger.debug("No addresses, return empty list of ids.")
        return ids

    # Get `mailaddr.id` of external addresses, ordered by priority
    sql = f"""SELECT id, email
               FROM mailaddr
              WHERE email IN {sqlquote(addresses)}
           ORDER BY priority DESC"""
    logger.debug(f"[SQL] Query external addresses: \n{sql}")

    try:
        qr = conn.execute(sql)
        qr_addresses = qr.fetchall()
    except Exception as e:
        logger.error(f"Error while getting list of id of external addresses: {repr(e)}, SQL: {sql}")
        return ids

    if qr_addresses:
        ids = [int(r.id) for r in qr_addresses]

    if not ids:
        # don't waste time if we don't even have senders stored in sql db.
        logger.debug("No record found in SQL database.")
        return []
    else:
        logger.debug(f"Addresses (in `mailaddr`): {qr_addresses}")
        return ids


def get_id_of_local_addresses(conn, addresses):
    """Return list of `users.id` of local addresses."""

    # Get `users.id` of local addresses
    sql = f"""SELECT id, email
               FROM users
              WHERE email IN {sqlquote(addresses)}
           ORDER BY priority DESC"""
    logger.debug(f"[SQL] Query local addresses: \n{sql}")

    ids = []
    try:
        qr = conn.execute(sql)
        qr_addresses = qr.fetchall()
        if qr_addresses:
            ids = [int(r.id) for r in qr_addresses]
            logger.debug(f"Local addresses (in `amavisd.users`): {qr_addresses}")
    except Exception as e:
        logger.error(f"Error while executing SQL command: {repr(e)}")

    if not ids:
        # don't waste time if we don't have any per-recipient wblist.
        logger.debug("No record found in SQL database.")
        return []
    else:
        return ids


def apply_inbound_wblist(conn, sender_ids, recipient_ids):
    # Return if no valid sender or recipient id.
    if not (sender_ids and recipient_ids):
        logger.debug("No valid sender id or recipient id.")
        return SMTP_ACTIONS["default"]

    # Get wblist
    sql = f"""SELECT rid, sid, wb
               FROM wblist
              WHERE sid IN {sqlquote(sender_ids)} AND rid IN {sqlquote(recipient_ids)}"""
    logger.debug(f"[SQL] Query inbound wblist (in `wblist`): \n{sql}")
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logger.debug("No wblist found.")
        return SMTP_ACTIONS["default"]

    logger.debug(f"Found inbound wblist: {wblists}")

    # Check sender addresses
    # rids/recipients are orded by priority
    for rid in recipient_ids:
        # sids/senders are sorted by priority
        for sid in sender_ids:
            if (rid, sid, "W") in wblists:
                logger.info(f"Whitelisted: wblist=({rid}, {sid}, 'W')")
                return SMTP_ACTIONS["whitelist"]

            if (rid, sid, "B") in wblists:
                logger.info(f"Blacklisted: wblist=({rid}, {sid}, 'B')")
                return reject_action

    return SMTP_ACTIONS["default"]


def apply_outbound_wblist(conn, sender_ids, recipient_ids):
    # Return if no valid sender or recipient id.
    if not (sender_ids and recipient_ids):
        logger.debug("No valid sender id or recipient id.")
        return SMTP_ACTIONS["default"]

    # Bypass outgoing emails.
    if settings.WBLIST_BYPASS_OUTGOING_EMAIL:
        logger.debug("Bypass outgoing email as defined in WBLIST_BYPASS_OUTGOING_EMAIL.")
        return SMTP_ACTIONS["default"]

    # Get wblist
    sql = f"""SELECT rid, sid, wb
                FROM outbound_wblist
               WHERE sid IN {sqlquote(sender_ids)} AND rid IN {sqlquote(recipient_ids)}"""
    logger.debug(f"[SQL] Query outbound wblist: \n{sql}")
    qr = conn.execute(sql)
    wblists = qr.fetchall()

    if not wblists:
        # no wblist
        logger.debug("No wblist found.")
        return SMTP_ACTIONS["default"]

    logger.debug(f"Found outbound wblist: {wblists}")

    # Check sender addresses
    # rids/recipients are orded by priority
    for sid in sender_ids:
        for rid in recipient_ids:
            if (rid, sid, "W") in wblists:
                logger.info(f"Whitelisted: outbound_wblist=({rid}, {sid}, 'W')")
                return SMTP_ACTIONS["default"] + f" outbound_wblist=({rid}, {sid}, 'W')"

            if (rid, sid, "B") in wblists:
                logger.info(f"Blacklisted: outbound_wblist=({rid}, {sid}, 'B')")
                return reject_action

    return SMTP_ACTIONS["default"]


def restriction(**kwargs):
    conn = kwargs["conn_amavisd"]
    conn_vmail = kwargs["conn_vmail"]

    if not conn:
        logger.error("Error, no valid Amavisd database connection.")
        return SMTP_ACTIONS["default"]

    # Get sender and recipient
    sender = kwargs["sender_without_ext"]
    sender_domain = kwargs["sender_domain"]
    recipient = kwargs["recipient_without_ext"]
    recipient_domain = kwargs["recipient_domain"]

    if kwargs["sasl_username"]:
        # Use sasl_username as sender for outgoing email
        sender = kwargs["sasl_username"]
        sender_domain = kwargs["sasl_username_domain"]

    if not sender:
        logger.debug("SKIP: no sender address.")
        return SMTP_ACTIONS["default"]

    if sender == recipient:
        logger.debug("SKIP: Sender is same as recipient.")
        return SMTP_ACTIONS["default"]

    valid_senders = get_policy_addresses_from_email(mail=sender)
    valid_recipients = get_policy_addresses_from_email(mail=recipient)

    if not kwargs["sasl_username"]:
        # Sender `username@*`
        sender_username = sender.split("@", 1)[0]
        if "+" in sender_username:
            valid_senders.append(sender_username.split("+", 1)[0] + "@*")
        else:
            valid_senders.append(sender_username + "@*")

    # Append original IP address
    client_address = kwargs["client_address"]
    valid_senders.append(client_address)

    # Append all possible wildcast IP addresses
    if is_ipv4(client_address):
        valid_senders += wildcard_ipv4(client_address)

    alias_target_sender_domain = get_alias_target_domain(alias_domain=sender_domain, conn=conn_vmail)
    if alias_target_sender_domain:
        _mail = sender.split("@", 1)[0] + "@" + alias_target_sender_domain
        valid_senders += get_policy_addresses_from_email(mail=_mail)

    alias_target_rcpt_domain = get_alias_target_domain(alias_domain=recipient_domain, conn=conn_vmail)
    if alias_target_rcpt_domain:
        _mail = recipient.split("@", 1)[0] + "@" + alias_target_rcpt_domain
        valid_recipients += get_policy_addresses_from_email(mail=_mail)

    logger.debug(f"Possible policy senders: {valid_senders}")
    logger.debug(f"Possible policy recipients: {valid_recipients}")

    check_outbound = False
    if (not check_outbound) and kwargs["sasl_username"]:
        check_outbound = True

    sender_domain_is_local = is_local_domain(conn=conn_vmail, domain=sender_domain, include_alias_domain=False)
    if (not check_outbound) and (alias_target_sender_domain or sender_domain_is_local):
        check_outbound = True

    id_of_client_cidr_networks = []
    client_cidr_network_checked = False

    # Outbound
    if check_outbound:
        logger.debug("Apply wblist for outbound message.")

        id_of_local_addresses = get_id_of_local_addresses(conn, valid_senders)

        id_of_ext_addresses = []
        if id_of_local_addresses:
            id_of_ext_addresses = get_id_of_external_addresses(conn, valid_recipients)

            id_of_client_cidr_networks = get_id_of_possible_cidr_network(conn, client_address)
            client_cidr_network_checked = True

        action = apply_outbound_wblist(conn,
                                       sender_ids=id_of_local_addresses + id_of_client_cidr_networks,
                                       recipient_ids=id_of_ext_addresses)

        if not action.startswith("DUNNO"):
            return action

    check_inbound = False
    if (not check_inbound) and (not kwargs["sasl_username"]):
        check_inbound = True

    if (not check_inbound) and kwargs["sasl_username"] and (sender_domain == recipient_domain):
        # Local user sends to another user in same domain
        check_inbound = True

    rcpt_domain_is_local = is_local_domain(conn=conn_vmail, domain=recipient_domain, include_alias_domain=False)
    if (not check_inbound) and (alias_target_rcpt_domain or rcpt_domain_is_local):
        # Local user sends to another local user in different domain
        check_inbound = True

    if check_inbound:
        logger.debug("Apply wblist for inbound message.")

        id_of_ext_addresses = []
        id_of_local_addresses = get_id_of_local_addresses(conn, valid_recipients)
        if id_of_local_addresses:
            id_of_ext_addresses = get_id_of_external_addresses(conn, valid_senders)

            if not client_cidr_network_checked:
                id_of_client_cidr_networks = get_id_of_possible_cidr_network(conn, client_address)

        action = apply_inbound_wblist(conn,
                                      sender_ids=id_of_ext_addresses + id_of_client_cidr_networks,
                                      recipient_ids=id_of_local_addresses)

        if not action.startswith("DUNNO"):
            return action

    return SMTP_ACTIONS["default"]
