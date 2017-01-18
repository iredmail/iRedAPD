# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Use specified transport for matched recipients.
#
# How to use this plugin:
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#    plugins = ['custom_spam_trap', ...]
#
# *) Add required parameters in /opt/iredapd/settings.py:
#
#	# List all spam trap accounts here. Wildcard address like 'spam@',
#       # 'trap@' is supported.
#	SPAM_TRAP_ACCOUNTS = ['spam-trap@mydomain.com']
#
#	# Define the smtp action for emails sent to spam trap account.
#	# We use the new transport '127.0.0.1:10028' defined in Postfix to
#	# handle them.
#	# Reference: http://www.postfix.org/access.5.html
#	SPAM_TRAP_SMTP_ACTION = 'FILTER smtp:[127.0.0.1]:10028'
#
#	# Define the plugin priority. 100 is highest, 0 is lowest.
#	PLUGIN_PRIORITIES['custom_spam_trap'] = 100
#
# *) Restart iRedAPD service.

from libs.logger import logger
from libs import SMTP_ACTIONS
import settings


def restriction(**kwargs):
    recipient = kwargs['recipient']

    if recipient in settings.SPAM_TRAP_ACCOUNTS:
        logger.debug('Spam trap recipient found: %s.' % recipient)
        return settings.SPAM_TRAP_SMTP_ACTION

    for rcpt in settings.SPAM_TRAP_ACCOUNTS:
        if rcpt.endswith('@'):
            if recipient.startswith(rcpt):
                logger.debug('Spam trap recipient found (matches: %s): %s.' % (rcpt, recipient))
                return settings.SPAM_TRAP_SMTP_ACTION

    return SMTP_ACTIONS['default']
