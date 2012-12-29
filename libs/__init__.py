__author__ = 'Zhang Huangbin <zhb@iredmail.org>'
__version__ = '1.3.9'

SMTP_ACTIONS = {'accept': 'OK',
                'defer': 'DEFER_IF_PERMIT Service temporarily unavailable',
                'reject': 'REJECT Not authorized',
                'default': 'DUNNO',
               }

ACCESS_POLICIES_OF_MAIL_LIST = {
    'public': 'Unrestricted',
    'domain': 'Only users under same domain are allowed',
    'subdomain': 'Only users under same domain and sub domains are allowed',
    'membersonly': 'Only members are allowed',
    'members': 'Only members are allowed',
    'moderatorsonly': 'Only moderators are allowed',
    'moderators': 'Only moderators are allowed',
    'allowedonly': 'Only moderators are allowed',
    'membersandmoderatorsonly': 'Only members and moderators are allowed',
}
