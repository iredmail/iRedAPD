# must have privilege to insert/update/delete sql records
vmail_db_user = 'vmailadmin'
vmail_db_password = 'DG6dIpNWYsDMmAsin0gobRooaULgDIoD'

# Domain name used for testing.
domain = 'test.com'
alias_domain = 'test-alias.com'
user = 'user@' + domain
user_in_alias_domain = 'user@' + alias_domain
user_alias = 'user-alias@' + domain
alias = 'alias@' + domain

ext_domain = 'external.com'
ext_user = 'user@' + ext_domain

sql_vars = {
    'domain': domain,
    'alias_domain': alias_domain,
    'user': user,
    'user_alias': user_alias,
    'alias': alias,
    'ext_domain': ext_domain,
    'ext_user': ext_user,
}

# rDNS names
rdns_subdomain_name = '.rdns.com'
rdns_exact_name = 'test' + rdns_subdomain_name

#########################################
# DO NOT TOUCH LINES BELOW
#########################################
from tests.tsettings import *
