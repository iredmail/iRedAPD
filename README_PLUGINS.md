iRedAPD is a Postfix policy server, please read Postfix document to understand
how it works:
[Postfix SMTP Access Policy Delegation](http://www.postfix.org/SMTPD_POLICY_README.html#protocol)

# For all plugins

If plugin needs to return `OK` (e.g. whitelisting), please do __NOT__ return
`OK` in Postfix protocol state `RCPT`, it may cause spam issues. Instead,
run your plugin in Postfix protocol state `END-OF-MESSAGE`.

## Custom plugins

### Name your custom plugins with string `custom_` prefixed

iRedAPD upgrade script will copy files/directories `plugins/custom_*` to new
version while upgrading, so please name your custom plugins (or its dependence)
with string `custom_` prefixed. For example, plugin `custom_spam_trap`,
`custom_wblist`, etc.

### [OPTIONAL] Define plugin priority for your custom plugins

Plugin priority is used to help iRedAPD apply plugins in ideal order. If no
priority defined, defaults to `0` (lowest), which means iRedAPD will apply
other plugins first, and your custom plugin will be the last one.

Priorities of built-in plugins are defined in `libs/__init__.py`, parameter
`PLUGIN_PRIORITIES`. You can define the priority of your own plugin in
iRedAPD config file `/opt/iredapd/settings.py`, this way it won't be overriden
after upgrading iRedAPD.

For example:

```
# Part of file: /opt/iredapd/settings.py

PLUGIN_PRIORITIES['custom_spam_trap'] = 100
PLUGIN_PRIORITIES['custom_wblist'] = 50
```

You can also change priorities for builtin plugins. for example:

```
PLUGIN_PRIORITIES['reject_null_sender'] = 90
```

## SMTP protocol state

Although Postfix has several protocol states, but we usually use two of them:
`RCPT`, `END-OF-MESSAGE`.

* `RCPT` is used in Postfix setting `smtpd_recipient_restrictions`.
* `END-OF-MESSAGE` is used in Postfix setting `smtpd_end_of_data_restrictions`.

Plugins are applied to Postfix protocol state `RCPT` by default,
if your plugin works in another protocol state, please explicitly set the
protocol state with variable `SMTP_PROTOCOL_STATE` in plugin file (e.g.
`plugins/custom_wblist.py`). For example:

```
SMTP_PROTOCOL_STATE = ['END-OF-MESSAGE']
```

If the plugin works in multiple protocol states, please list them all. For
example:

```
SMTP_PROTOCOL_STATE = ['RCPT', 'END-OF-MESSAGE']
```

# For plugins applied to only OpenLDAP backend

## If plugin requires sender or recipient to be local account

If your plugin is applied to local user, please add below variables in plugin file:

```
# Skip this plugin if sender is not local.
REQUIRE_LOCAL_SENDER = True

# Skip this plugin if recipient is not local.
REQUIRE_LOCAL_RECIPIENT = True
```

## If plugin relies on some LDAP attributes

If your plugin relies on some LDAP attributes defined in sender or recipient
object, please add below variables in plugin file, iRedAPD will query them
before applying the plugin, so that your plugin can use them directly:

```
# Attributes in sender object
SENDER_SEARCH_ATTRLIST = ['attr1', 'attr2', ...]

# Attributes in recipient object
RECIPIENT_SEARCH_ATTRLIST = ['attr1', 'attr2', ...]
```
