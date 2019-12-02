# Syslog server address.
# Log to local socket by default, /dev/log on Linux/OpenBSD, /var/run/log on FreeBSD.
SYSLOG_SERVER = '/dev/log'
SYSLOG_PORT = 514

# Syslog facility
SYSLOG_FACILITY = 'local5'

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

# DNS Query.
# Timeout in seconds. Must be a float number.
DNS_QUERY_TIMEOUT = 3.0

# Log smtp actions returned by plugins in SQL database (table `smtp_actions`).
LOG_SMTP_SESSIONS = True
LOG_SMTP_SESSIONS_EXPIRE_DAYS = 7

LOG_SMTP_SESSIONS_BYPASS_DUNNO = False
LOG_SMTP_SESSIONS_BYPASS_GREYLISTING = False
LOG_SMTP_SESSIONS_BYPASS_WHITELIST = False

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
WBLIST_DISCARD_INSTEAD_OF_REJECT = False

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
CHECK_SPF_IF_LOGIN_MISMATCH = True

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

# Bypass if sender server IP address is listed in sender domain SPF DNS record.
GREYLISTING_BYPASS_SPF = True

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

# Don't apply recipient throttling if both sender/recipient are hosted locally
# (they don't have to be in same domain)
THROTTLE_BYPASS_LOCAL_RECIPIENT = True

# Don't apply any throttling if both sender/recipient are hosted locally AND
# under same domain.
THROTTLE_BYPASS_SAME_DOMAIN = True

# ----------------
# Required by: plugins/senderscore.py
#
# Reject the email if senderscore equals to or is lower than this score.
SENDERSCORE_REJECT_SCORE = 30

# Cache the score returned by DNS query for how many days.
SENDERSCORE_CACHE_DAYS = 7

# ----------------
# Send mail
#
# Path to command `sendmail`. e.g. `/usr/sbin/sendmail`.
# Leave it empty to let system detect the path.
CMD_SENDMAIL = '/usr/sbin/sendmail'

# Recipients of notification email
NOTIFICATION_RECIPIENTS = ['root']

# SMTP server address, port, username, password used to send notification mail.
NOTIFICATION_SMTP_SERVER = 'localhost'
NOTIFICATION_SMTP_PORT = 587
NOTIFICATION_SMTP_STARTTLS = True
NOTIFICATION_SMTP_USER = 'no-reply@localhost.localdomain'
NOTIFICATION_SMTP_PASSWORD = ''
NOTIFICATION_SMTP_DEBUG_LEVEL = 0

# The short description or full name of this smtp user. e.g. 'No Reply'
NOTIFICATION_SENDER_NAME = 'No Reply'
