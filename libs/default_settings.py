# Trusted IP address or networks.
# Valid formats:
#   - Single IP address: 192.168.1.1
#   - Wildcard IP range: 192.168.1.*, 192.168.*.*, 192.168.*.1
#   - IP subnet: 192.168.1.0/24
MYNETWORKS = []

# ---------------
# Required by:
#   - plugins/amavisd_wblist.py
#   - plugins/throttling.py
#
# Query additional wildcard IP(v4) addresses for white/blacklists, throttling.
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
GREYLISTING_MESSAGE = 'Greylisting in effect, please try again later'

# --------------
# Required by: plugins/throttling.py
#
# Don't apply throttling on senders specified in `MYNETWORKS`.
THROTTLE_BYPASS_MYNETWORKS = False
