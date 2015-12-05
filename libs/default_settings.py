# Rotate log file based on file size or time: size, time. Default is 'time'.
LOGROTATE_TYPE = 'time'

# Save how many copies of rotated log files. Default is 12.
LOGROTATE_COPIES = 12

# Rotate when log file reaches specified file size. Default is 100MB (104857600)
# Used when rotate type is 'size'.
LOGROTATE_SIZE = 104857600

# Rotate interval. Used when rotate type is 'time'.
# Reference:
# https://docs.python.org/2/library/logging.handlers.html#timedrotatingfilehandler
#
#   Value	Type of interval
#   'S'         Seconds
#   'M'         Minutes
#   'H'         Hours
#   'D'         Days
#   'W0', 'W1', ... 'W6'    Weekday (W0 is Monday, W6 is Sunday)
#   'midnight'	Roll over at midnight
#
# Format: [interval]-[type_of_internval]. Samples:
#   - 30 minutes:       '30-M'
#   - 1 hour:           '1-H'
#   - 1 day:            '1-D'
#   - every Sunday:     'W6'    # (W0 is Monday)
#   - every midnight:   '1-midnight'
#   - every 3 midnight: '3-midnight'
LOGROTATE_INTERVAL = 'W6'

# Priority for third-party plugins, or override pre-defined priorities in
# libs/__init__.py.
#
# Plugin with smaller number has higher priority and will be applied first.
# Sample setting:
#
#   PLUGIN_PRIORITIES = {'plugin_name_1', 100,
#                        'plugin_name_2', 200}
PLUGIN_PRIORITIES = {}

# Trusted IP address or networks.
# Valid formats:
#   - Single IP address: 192.168.1.1
#   - Wildcard IP range: 192.168.1.*, 192.168.*.*, 192.168.*.1
#   - IP subnet: 192.168.1.0/24
MYNETWORKS = []

# ---------------
# Required by:
#   - plugins/amavisd_wblist.py
#   - plugins/throttle.py
#
# Query additional wildcard IP(v4) addresses for white/blacklists, throttle.
# For example, for client address 'w.x.y.z', if this option is disabled (False),
# it just query 'w.x.y.z', 'w.x.y.*' and 'w.x.*.z' (wildcard). If enabled (True),
# it will replace all possible fields by '*' as wildcard:
#   w.x.y.z, w.x.y.*, w.x.*.z, w.*.y.z, *.x.y.z, w.x.*.*, w.*.*.*, ...
ENABLE_ALL_WILDCARD_IP = True

# ---------------
# Required by: plugins/amavisd_wblist.py
#
# Don't check white/blacklists for outgoing emails sent by sasl authenticated user.
WBLIST_BYPASS_OUTGOING_EMAIL = False

# ---------------
# Required by:
#   - plugins/sql_force_change_password_in_days.py
#   - plugins/ldap_force_change_password_in_days.py
#
# Force to change password in certain days.
CHANGE_PASSWORD_DAYS = 90

# Reject reason.
# It's recommended to add URL of the web applications which user can login
# to change password in this message. e.g. Roundcube webmail, iRedAdmin-Pro.
CHANGE_PASSWORD_MESSAGE = 'Password expired or never changed, please change your password in webmail before sending email'

# Allow certain users or domains to never change password.
# sample values: ['user@example.com', 'domain.com']
CHANGE_PASSWORD_NEVER_EXPIRE_USERS = []

# --------------
# Required by: plugins/reject_sender_login_mismatch.py
#
# Check whether sender is forged on message which sent without smtp auth.
CHECK_FORGED_SENDER = True

# Allowed messages with below forged addresses
ALLOWED_FORGED_SENDERS = []

# Allowed senders or sender domains.
#
# If you want to allow someone to send email as forged address, e.g.
# salesforce.com, you can bypass these addresses in this setting.
# Default value is empty (no allowed forged sender).
#
# Sample setting: allow local user `user@local_domain_1.com` and all users
# under `local_domain_2.com` to send email as other users.
#
#   ALLOWED_FORGED_SENDERS = ['user@local_domain_1.com', 'local_domain_2.com']
#
ALLOWED_LOGIN_MISMATCH_SENDERS = []

# Strictly allow sender to send as one of user alias addresses. Default is True.
ALLOWED_LOGIN_MISMATCH_STRICTLY = True

# Allow member of mail lists/alias account to send email as mail list/alias
# ('From: <email_of_mail_list>' in mail header). Default is False.
ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = False

# --------------
# Required by: plugins/greylisting.py
#
# Reject reason for greylisting.
GREYLISTING_MESSAGE = 'Intended policy rejection, please try again later'

# Number of MINUTES to wait before client retrying.
# Temporarily reject if client retries in specified time.
GREYLISTING_BLOCK_EXPIRE = 15

# Disable greylisting in DAYS for clients which successfully passed
# greylisting (retried and delivered). It's also used to clean up old
# greylisting tracking records.
GREYLISTING_AUTH_TRIPLET_EXPIRE = 30

# Delete tracking record x DAYS after block_expire time, if no successful
# attempt was made.
GREYLISTING_UNAUTH_TRIPLET_EXPIRE = 2

# --------------
# Required by: plugins/throttle.py
#
# Don't apply throttle settings on senders specified in `MYNETWORKS`.
THROTTLE_BYPASS_MYNETWORKS = False

# --------------
# Required by: tools/cleanup_db.py
#
# Show senders which not yet passed greylisting.
CLEANUP_SHOW_TOP_GREYLISTED_DOMAINS = True
CLEANUP_NUM_OF_TOP_GREYLISTED_DOMAINS = 30
