# Trusted or internal networks.
MYNETWORKS = []

# ---------------
# Required by:
#   - plugins/sql_force_change_password_in_days.py
#   - plugins/ldap_force_change_password_in_days.py
# Force to change password in certain days.
CHANGE_PASSWORD_DAYS = 90

# Reject reason.
# It's recommended to add URL of the web applications which user can login
# to change password in this message. e.g. Roundcube webmail, iRedAdmin-Pro.
CHANGE_PASSWORD_MESSAGE = 'Please change your password in webmail before sending email'

# --------------
# Required by: plugins/reject_sender_login_mismatch.py
# Allowed senders or sender domains.
ALLOWED_LOGIN_MISMATCH_SENDERS = []

# Strictly allow sender to send as one of user alias addresses. Default is True.
ALLOWED_LOGIN_MISMATCH_STRICTLY = True

# Allow member of mail lists/alias account to send email as mail list/alias
# ('From: <email_of_mail_list>' in mail header). Default is False.
ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = False
