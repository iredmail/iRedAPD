__version__ = '1.3.8'

SMTP_ACTIONS = {'accept': 'DUNNO',
                'defer': 'DEFER_IF_PERMIT Service temporarily unavailable',
                'reject': 'REJECT Not authorized',
                'default': 'DUNNO',
               }
