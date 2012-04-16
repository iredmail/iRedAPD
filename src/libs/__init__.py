__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.3.7'

SMTP_ACTIONS = {'accept': 'DUNNO',
                'defer': 'DEFER_IF_PERMIT Service temporarily unavailable',
                'reject': 'REJECT Not authorized',
                'default': 'DUNNO',
               }
