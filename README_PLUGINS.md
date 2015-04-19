
Read Postfix document for more details if you want to develop plugin for iRedAPD:
[Postfix SMTP Access Policy Delegation](http://www.postfix.org/SMTPD_POLICY_README.html#protocol)

# For all plugins

## SMTP protocol state

Plugins are applied to Postfix protocol state `RCPT` by default, 
if your plugin works in another protocol state, please explicitly set the
protocol state with variable `SMTP_PROTOCOL_STATE` in plugin file. For example:

    SMTP_PROTOCOL_STATE = 'END-OF-MESSAGE'

Although Postfix has several protocol states, but we usually use two of them:
`RCPT`, `END-OF-MESSAGE`.

* `RCPT` is used in Postfix setting `smtpd_sender_restrictions` or
  `smtpd_recipient_restrictions`, do NOT enable iRedAPD in BOTH of them.

* `END-OF-MESSAGE` is used in Postfix setting `smtpd_end_of_data_restrictions`.

# For plugins applied to LDAP backend

## If plugin requires sender or recipient to be local account

If your plugin requires sender or recipient to be local account, please add
below variables in plugin file:

    # Skip this plugin if sender is not local.
    REQUIRE_LOCAL_SENDER = True

    # Skip this plugin if recipient is not local.
    REQUIRE_LOCAL_RECIPIENT = True

## If plugin requires specified LDAP attributes

If your plugin requires some LDAP attributes in sender or recipient object,
please add below variables in plugin file:

    # Attributes in sender object
    SENDER_SEARCH_ATTRLIST = ['attr_name_1', 'attr_name_2', ...]

    # Attributes in recipient object
    RECIPIENT_SEARCH_ATTRLIST = ['attr_name_1', 'attr_name_2', ...]
