__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.3.8'

SMTP_ACTIONS = {'accept': 'OK',
                'defer': 'DEFER_IF_PERMIT Service temporarily unavailable',
                'reject': 'REJECT Not authorized',
                'default': 'DUNNO',
               }
