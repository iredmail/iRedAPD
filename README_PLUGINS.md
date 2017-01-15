iRedAPD is a Postfix policy server, please read Postfix document to understand
how it works:
[Postfix SMTP Access Policy Delegation](http://www.postfix.org/SMTPD_POLICY_README.html#protocol)

# For all plugins

## Custom plugins

### Name your custom plugins with string `custom_` prefixed

iRedAPD upgrade script will copy files/directories `plugins/custom_*` to new
version while upgrading, so please name your custom plugins (or its dependence)
with string `custom_` prefixed, for example, plugin `custom_spam_trap`,
`custom_wblist`, etc.

### Define plugin priority for your custom plugins

Plugin priority is used to help iRedAPD apply plugins in ideal order. If no
priority defined, defaults to 0 (lowest).

Priorities of built-in plugins are defined in `libs/__init__.py`, parameter
`PLUGIN_PRIORITIES`. You should define the priority of your own plugin in
iRedAPD config file `/opt/iredapd/settings.py`, so that it won't be overriden
after upgrading iRedAPD.

Sample priorities (in `/opt/iredapd/settings.py`):

```
PLUGIN_PRIORITIES['custom_spam_trap'] = 100
PLUGIN_PRIORITIES['custom_wblist'] = 50
```

You can also use different priority for builtin plugins. for example:

```
PLUGIN_PRIORITIES['reject_null_sender'] = 90
```

## SMTP protocol state

Plugins are applied to Postfix protocol state `RCPT` by default,
if your plugin works in another protocol state, please explicitly set the
protocol state with variable `SMTP_PROTOCOL_STATE` in plugin file. For example:

```
SMTP_PROTOCOL_STATE = ['END-OF-MESSAGE']
```

If the plugin works in multiple protocol states, please list them all. For
example:

```
SMTP_PROTOCOL_STATE = ['RCPT', 'END-OF-MESSAGE']
```

Although Postfix has several protocol states, but we usually use two of them:
`RCPT`, `END-OF-MESSAGE`.

* `RCPT` is used in Postfix setting `smtpd_sender_restrictions` or
  `smtpd_recipient_restrictions`, do NOT enable iRedAPD in BOTH of them.

* `END-OF-MESSAGE` is used in Postfix setting `smtpd_end_of_data_restrictions`.

# For plugins applied to OpenLDAP backend

## If plugin requires sender or recipient to be local account

If your plugin requires sender or recipient to be local account, please add
below variables in plugin file:

```
# Skip this plugin if sender is not local.
REQUIRE_LOCAL_SENDER = True

# Skip this plugin if recipient is not local.
REQUIRE_LOCAL_RECIPIENT = True
```

## If plugin requires specified LDAP attributes

If your plugin requires some LDAP attributes in sender or recipient object,
please add below variables in plugin file:

```
# Attributes in sender object
SENDER_SEARCH_ATTRLIST = ['attr_name_1', 'attr_name_2', ...]

# Attributes in recipient object
RECIPIENT_SEARCH_ATTRLIST = ['attr_name_1', 'attr_name_2', ...]
```
