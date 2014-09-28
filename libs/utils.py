import re
import logging
from libs import SMTP_ACTIONS

# Mail address. +, = is used in SRS rewritten addresses.
regx_email = r'''[\w\-][\w\-\.\+\=]*@[\w\-][\w\-\.]*\.[a-zA-Z]{2,15}'''

# Domain name
regx_domain = r'''[\w\-][\w\-\.]*\.[a-z]{2,15}'''


def apply_plugin(plugin, **kwargs):
    action = SMTP_ACTIONS['default']

    logging.debug('--> Apply plugin: %s' % plugin.__name__)
    try:
        action = plugin.restriction(**kwargs)
        logging.debug('<-- Result: %s' % action)
    except Exception, e:
        logging.debug('<!> Error: %s' % str(e))

    return action


def is_email(s):
    try:
        s = str(s).strip()
    except UnicodeEncodeError:
        return False

    # Not contain invalid characters and match regular expression
    if not set(s) & set(r'~!#$%^&*()\/ ') \
       and re.compile(regx_email + '$', re.IGNORECASE).match(s):
        return True

    return False


def is_domain(s):
    s = str(s)
    if len(set(s) & set('~!#$%^&*()+\\/\ ')) > 0 or '.' not in s:
        return False

    comp_domain = re.compile(regx_domain + '$', re.IGNORECASE)
    if comp_domain.match(s):
        return True
    else:
        return False
