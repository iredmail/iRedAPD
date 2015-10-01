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
#     compare it with current date. if password last change date is longer
#     than specified days, this plugin rejects smtp session with specified
#     message.

import datetime
from libs.logger import logger
import settings
from libs import SMTP_ACTIONS


reject_action = 'REJECT ' + settings.CHANGE_PASSWORD_MESSAGE

def restriction(**kwargs):
    if not kwargs['sasl_username']:
        return 'DUNNO Not a local user'

    sasl_username = kwargs['sasl_username']
    sasl_username_domain = kwargs['sasl_username_domain']

    # Bypass allowed senders.
    if sasl_username in settings.CHANGE_PASSWORD_NEVER_EXPIRE_USERS \
       or sasl_username_domain in settings.CHANGE_PASSWORD_NEVER_EXPIRE_USERS:
        return 'DUNNO User or domain is allowed to never change password.'

    # Get `mailbox.passwordlastchange`.
    sql = """SELECT passwordlastchange FROM mailbox WHERE username='%s' LIMIT 1""" % sasl_username
    logger.debug('SQL to get mailbox.passwordlastchange of sender (%s): %s' % (sasl_username, sql))

    conn = kwargs['conn_vmail']
    qr = conn.execute(sql)
    sql_record = qr.fetchone()
    logger.debug('Returned SQL Record: %s' % str(sql_record))

    if sql_record:
        pwchdate = sql_record[0]
        logger.debug('Date of password last change: %s' % str(pwchdate))
        if not pwchdate:
            pwchdate = datetime.datetime(1970, 1, 1, 0, 0, 0)
    else:
        logger.debug('No SQL record of this user.')
        return SMTP_ACTIONS['default']

    # Compare date to make sure it's less than CHANGE_PASSWORD_DAYS.
    shift = datetime.datetime.now() - pwchdate
    if shift < datetime.timedelta(days=settings.CHANGE_PASSWORD_DAYS):
        logger.debug("Current password was changed in %d days." % settings.CHANGE_PASSWORD_DAYS)
        return SMTP_ACTIONS['default']
    else:
        logger.debug("Sender didn't change password in last %d days." % settings.CHANGE_PASSWORD_DAYS)
        return reject_action

    logger.debug("Sender will be forced to change password on %s." % str(pwchdate + datetime.timedelta(days=settings.CHANGE_PASSWORD_DAYS)))
    return SMTP_ACTIONS['default']
