# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose: Check date of user password last change and reject smtp session if
#          user didn't change password in 90 days.
#
# Below settings can be placed in iRedAPD config file 'settings.py':
#
#   - CHANGE_PASSWORD_DAYS: value must be an integer number. e.g. 90 (90 days)
#   - CHANGE_PASSWORD_MESSAGE: message string which will be read by user
#
# Sample settings:
#
#   - CHANGE_PASSWORD_DAYS = 90
#   - CHANGE_PASSWORD_MESSAGE = 'Please change your password in webmail immediately: https://xxx/webmail/'
#
# How it works:
#
#   - iRedMail configures plugin 'password' of Roundcube webmail to store
#     password change date in SQL database `vmail`, column
#     `mailbox.passwordlastchange`.
#
#   - This plugin checks date stored in `mailbox.passwordlastchange` and
#     compare it with current date.

import datetime
import logging
import settings
from libs import SMTP_ACTIONS

REQUIRE_LOCAL_SENDER = True
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = ['shadowLastChange']
RECIPIENT_SEARCH_ATTRLIST = []

# You can override below two settings in iRedAPD config file 'settings.py'.
# Force to change password in 90 days.
try:
    CHANGE_PASSWORD_DAYS = settings.CHANGE_PASSWORD_DAYS
except:
    CHANGE_PASSWORD_DAYS = 90

# Reject reason.
# It's recommended to add URL of your webmail in this message.
try:
    CHANGE_PASSWORD_MESSAGE = settings.CHANGE_PASSWORD_MESSAGE
except:
    CHANGE_PASSWORD_MESSAGE = 'Please change your password in webmail before sending email'

reject_action = 'REJECT ' + CHANGE_PASSWORD_MESSAGE


def get_days_of_today():
    """Return number of days since 1970-01-01."""
    today = datetime.date.today()

    try:
        return (datetime.date(today.year, today.month, today.day) - datetime.date(1970, 1, 1)).days
    except:
        return 0


def restriction(**kwargs):
    if not kwargs['sasl_username']:
        logging.debug('DUNNO Not an authenticated user (no sasl_username in smtp session)')
        return 'DUNNO Not an authenticated user (no sasl_username in smtp session)'

    if not kwargs['sender_ldif']:
        logging.debug('DUNNO Not a local user (no sender ldif)')
        return 'DUNNO Not a local user (no sender ldif)'

    sender_ldif = kwargs['sender_ldif']

    # Get (an integer) value of attribute 'shadowLastChange'.
    shadow_last_change = int(sender_ldif.get('shadowLastChange', [0])[0])
    days_of_today = get_days_of_today()

    # Days since password last change
    passed_days = days_of_today - shadow_last_change

    logging.debug('Days of password last change: %d (today: %d)' % (shadow_last_change, days_of_today))

    if passed_days >= CHANGE_PASSWORD_DAYS:
        logging.debug("Password last change date is older than %d days." % CHANGE_PASSWORD_DAYS)
        return reject_action

    logging.debug("Sender will be forced to change password in %d day(s)." % (CHANGE_PASSWORD_DAYS - passed_days))
    return SMTP_ACTIONS['default']
