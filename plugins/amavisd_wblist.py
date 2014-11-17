# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Reject senders listed in per-user blacklists, bypass senders listed
#          in per-user whitelists stored in Amavisd database (@lookup_sql_dsn).
#
# Note: Amavisd is configured to be an after-queue content filter in iRedMail.
#       with '@lookup_sql_dsn' setting enabled in Amavisd config file, Amavisd
#       will query per-recipient, per-domain and server-wide (a.k.a. catch-all)
#       policy rules stored in SQL table `policy`.
#
#       if you don't enable this plugin, Amavisd will quarantine emails sent
#       from per-user blacklisted senders, and no spam/virus scanning for
#       emails sent from per-user whitelisted senders. With this plugin,
#       we can tell Postfix to reject blacklisted sender BEFORE email enter
#       mail queue, or bypass emails directly.
#
# How to use this plugin:
#
# *) Enable `@lookup_sql_dsn` in Amavisd config file.
#
# *) Set Amavisd lookup SQL database related parameters (amavisd_db_*) in
#    iRedAPD config file `settings.py`, and enable this plugin.
#
# *) Enable iRedAPD in Postfix `smtpd_end_of_data_restrictions`.
#    For example:
#
#    smtpd_end_of_data_restrictions =
#           check_policy_service inet:[127.0.0.1]:7777,
#           ...
#
# *) Enable this plugin in iRedAPD config file (/opt/iredapd/settings.py).
# *) Restart both iRedAPD and Postfix services.

import logging
from libs import SMTP_ACTIONS
from libs.amavisd import core as amavisd_lib

# Connect to amavisd database
REQUIRE_AMAVISD_DB = True


def restriction(**kwargs):
    adb_cursor = kwargs['amavisd_db_cursor']

    if not adb_cursor:
        logging.debug('Error, no valid Amavisd database connection.')
        return SMTP_ACTIONS['default']

    sender = kwargs['sender']
    sender_domain = kwargs['sender_domain']
    recipient = kwargs['recipient']
    recipient_domain = kwargs['recipient_domain']

    valid_senders = amavisd_lib.get_valid_addresses_from_email(sender, sender_domain)
    valid_recipitns = amavisd_lib.get_valid_addresses_from_email(recipient, recipient_domain)

    logging.debug('Possible senders: %s' % str(valid_senders))
    logging.debug('Possible recipients: %s' % str(valid_recipitns))

    logging.debug('Query per-user, per-domain and global white/blacklists.')
    # wblist priority:
    #   1: per-user (user@domain.com)
    #   2: per-domain (@domain.com)
    #   3: global (@.)
    # Get possible senders
    #SELECT id FROM users where email IN ('postmaster@a.cn','postmaster','@a.cn','@.a.cn','@.cn','@.') ORDER BY priority;
    # Get mailaddr.id for all possible senders
    #select id as sid from mailaddr;

    return SMTP_ACTIONS['default']
