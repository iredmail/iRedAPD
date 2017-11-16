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

# Recipient delimiters. If you have multiple delimiters, please list them all.
RECIPIENT_DELIMITERS = ['+']

# SQLAlchemy: The size of the SQL connection pool to be maintained.
# This is the largest number of connections that will be kept persistently in
# the pool. Note that the pool begins with no connections; once this number of
# connections is requested, that number of connections will remain.
# Can be set to 0 to indicate no size limit.
SQL_CONNECTION_POOL_SIZE = 10

# SQLAlchemy: SQL connection max overflow
# The maximum overflow size of the pool.
# When the number of checked-out connections reaches the size set in pool_size,
# additional connections will be returned up to this limit. When those
# additional connections are returned to the pool, they are disconnected and
# discarded. It follows then that the total number of simultaneous connections
# the pool will allow is pool_size + max_overflow, and the total number of
# `sleeping` connections the pool will allow is pool_size. max_overflow can be
# set to -1 to indicate no overflow limit; no limit will be placed on the total
# number of concurrent connections. Defaults to 10.
SQL_CONNECTION_MAX_OVERFLOW = 10

# SQLAlchemy: SQL connection recycle
# This parameter prevents the pool from using a particular connection that has
# passed a certain age (in seconds), and is appropriate for database backends
# such as MySQL that automatically close connections that have been stale after
# a particular period of time.
SQL_CONNECTION_POOL_RECYCLE = 60

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
ENABLE_ALL_WILDCARD_IP = False

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
# Check whether sender is forged in message sent without smtp auth.
CHECK_FORGED_SENDER = True

# If you allow someone or some service providers to send email as forged
# (your local) address, you can list all allowed addresses in this parameter.
# For example, if some ISPs may send email as 'user@mydomain.com' (mydomain.com
# is hosted on your server) to you, you should add `user@mydomain.com` as one
# of forged senders.
# Sample: ALLOWED_FORGED_SENDERS = ['user@mydomain.com', 'mydomain.com']
ALLOWED_FORGED_SENDERS = []

# Check DNS SPF record of sender domain if sender login mismatch.
# This is useful if sender also sends email from a email service vendor.
CHECK_SPF_IF_LOGIN_MISMATCH = False

# Allow sender login mismatch for specified senders or sender domains.
#
# Sample setting: allow local user `user@local_domain_1.com` and all users
# under `local_domain_2.com` to send email as other users.
#
#   ALLOWED_LOGIN_MISMATCH_SENDERS = ['user@mydomain1.com', 'mydomain2.com']
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
GREYLISTING_MESSAGE = 'Intentional policy rejection, please try again later'

# Training mode.
# Greylisting plugin still analyze incoming emails and stores tracking info
# in SQL database for greylisting purpose, but it doesn't reject emails.
GREYLISTING_TRAINING_MODE = False

# Time (in MINUTES) to wait before client retrying, client will be rejected if
# retires too soon (in less than specified minutes). Defaults to 15 minutes.
GREYLISTING_BLOCK_EXPIRE = 15

# If sender server passed greylisting, whitelist it for given DAYS.
# Older triplets will be cleaned up from SQL database. Defaults to 30 days.
GREYLISTING_AUTH_TRIPLET_EXPIRE = 30

# Time (in DAYS) to keep tracking records if client didn't pass the
# greylisting and no further deliver attempts. Defaults to `1` day.
GREYLISTING_UNAUTH_TRIPLET_EXPIRE = 1

# --------------
# Required by: plugins/whitelist_outbound_recipient.py
#
# Whitelist outbound recipient for greylisting service.
#
# Note: Default is whitelisting recipient email address for the (local) sender,
#          +----------------------------+
#       so | it's a per-user whitelist. | If you want to whitelist whole
#          +----------------------------+
#       recipient domain globally, please check setting
#       `WL_RCPT_WHITELIST_DOMAIN_FOR_GREYLISTING` below.
WL_RCPT_FOR_GREYLISTING = True

# Whitelist sender directly (no SPF query).
# Requires options `WL_RCPT_LOCAL_ACCOUNT` and `WL_RCPT_RCPT` listed below.
WL_RCPT_WITHOUT_SPF = False

# Whitelist recipient directly (no SPF query) for local account:
#   - user: for the sender (per-user whitelist)
#   - domain: for the sender domain (per-domain whitelist)
#   - global: for global whitelist
WL_RCPT_LOCAL_ACCOUNT = 'user'

# Whitelist which recipient for local account
#   - user: the recipient (single email address)
#   - domain: the recipient domain
WL_RCPT_RCPT = 'user'

# Whitelist domain of recipient.
#
# Notes:
#
#   *) this will submit domain to SQL table
#      `iredapd.greylisting_whitelist_domains` and waiting for cron job
#      `spf_to_greylisting_whitelists.py` to whitelist IP addresses/networks
#      in SPF/MX/A records of the domain.
#
#      +----------------------- WARNING -----------------------------+
#   *) | The domain is whitelisted for greylisting service globally. |
#      +-------------------------------------------------------------+
#      This should be useful if your mail server just serve your own company.
WL_RCPT_WHITELIST_DOMAIN_FOR_GREYLISTING = False

# --------------
# Required by: plugins/throttle.py
#
# Don't apply throttle settings on senders specified in `MYNETWORKS`.
THROTTLE_BYPASS_MYNETWORKS = False
