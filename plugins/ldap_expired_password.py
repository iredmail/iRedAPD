# Author:   Zhang Huangbin <zhb _at_ iredmail.org>
# Purpose:  Force user to change account password in 90 days.

import datetime
from libs import SMTP_ACTIONS

REQUIRE_LOCAL_SENDER = True
REQUIRE_LOCAL_RECIPIENT = False
SENDER_SEARCH_ATTRLIST = ['shadowLastChange']
RECIPIENT_SEARCH_ATTRLIST = []

# Force mail user to change password in how many days. Default is 90.
EXPIRED_DAYS = 90

def restriction(**kwargs):
    sender_ldif = kwargs['sender_ldif']

    if not 'mailUser' in sender_ldif['objectClass']:
        return 'DUNNO Not a mail user'

    # Check password last change days
    last_changed_day = int(sender_ldif.get('shadowLastChange', [0])[0])

    # Convert today to shadowLastChange
    today = datetime.date.today()
    changed_days_of_today = (datetime.date(today.year, today.month, today.day) - datetime.date(1970, 1, 1)).days

    if (last_changed_day + EXPIRED_DAYS) < changed_days_of_today:
        return 'REJECT Password expired, please change your password before sending email.'

    return SMTP_ACTIONS['default']

