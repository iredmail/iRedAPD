# For all plugins

## SMTP protocol state

If your plugin is not applied in Postfix protocol state 'RCPT', please
add parameter 'SMTP_PROTOCOL_STATE' in plugin file. For example:

    SMTP_PROTOCOL_STATE = 'END-OF-MESSAGE'

Although Postfix has several protocol states, but we usually use two of them:
RCPT, END-OF-MESSAGE.

`RCPT` is used in Postfix parameter `smtpd_sender_restrictions` or
`smtpd_recipient_restrictions`.

`END-OF-MESSAGE' is used in Postfix parameter `smtpd_end_of_data_restrictions`.

Refer to Postfix document for more details:
[Postfix SMTP Access Policy Delegation](http://www.postfix.org/SMTPD_POLICY_README.html#protocol)

# For plugins applied to LDAP backend

## If plugin requires sender or recipient to be local account

If your plugin requires to sender or recipient to be local account, please add
below parameters in plugin file:

    # Require sender to be local
    REQUIRE_LOCAL_SENDER = True

    # Require recipient to be local
    REQUIRE_LOCAL_RECIPIENT = True

## If plugin requires some LDAP attributes

If your plugin requires to some LDAP attributes in sender or recipient object,
please add below parameters in plugin file:

    # Attributes in sender object
    SENDER_SEARCH_ATTRLIST = ['attr_name', 'attr_name_2', ...]

    # Attributes in recipient object
    RECIPIENT_SEARCH_ATTRLIST = ['attr_name', 'attr_name_2', ...]

If you don't need to query sender or recipient attributes, it's not necessary
to add them.
