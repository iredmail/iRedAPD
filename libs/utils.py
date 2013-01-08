import logging
from libs import SMTP_ACTIONS


def apply_plugin(plugin, **kwargs):
    action = SMTP_ACTIONS['default']

    logging.debug('--> Apply plugin: %s' % plugin.__name__)
    try:
        action = plugin.restriction(**kwargs)
        logging.debug('<-- Result: %s' % action)
    except Exception, e:
        logging.debug('<!> Error: %s' % str(e))

    return action

