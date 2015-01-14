# Introduction

* iRedAPD is a simple [Postfix policy server](http://www.postfix.org/SMTPD_POLICY_README.html), written in Python, with plugin support.
* iRedAPD listens on port `7777`, runs as a low-privileged user (`iredapd` by default).
* The latest iRedAPD works with OpenLDAP, MySQL/MariaDB and PostgreSQL backends.
* License: GPL v3 (except file libs/daemon.py, BSD style as mentioned in this file by file author).
* Author: Zhang Huangbin <zhb _at_ iredmail.org>.

**NOTES**: 

* iRedAPD is a sub-project of [iRedMail project](http://www.iredmail.org).
* iRedAPD is installed and enabled in iRedMail by default, so you don’t need
  this tutorial if you already have iRedMail running. Standalone installation
  guide is `INSTALL.md`.
* You can manage iRedAPD with iRedMail [web admin panel - iRedAdmin-Pro](http://www.iredmail.org/admin_panel.html).

# Available plugins

Plugins are files placed under `plugins/` directory, plugin name is file name
without file extension `.py`. It's recommended to read comment lines in plugin
source files to understand how it works and what it does.

## Plugins for all backends

* `reject_sender_login_mismatch`: Reject sender login mismatch (addresses in
  `From:` and SASL username). It will verify user alias addresses against
  SQL/LDAP database.

* `reject_null_sender`: Reject message submitted by sasl authenticated user but
  specifying null sender in `From:` header (`from=<>` in Postfix log).
  RECOMMEND to enable this plugin.

    If your user's password was cracked by spammer, spammer can use
    this account to bypass smtp authentication, but with a null sender
    in `From:` header, throttling won't be triggered.

* `amavisd_wblist`: Reject senders listed in per-user blacklists, bypass
  senders listed in per-user whitelists stored in Amavisd database.
  RECOMMEND to enable this plugin.

* `amavisd_message_size_limit`: Check per-recipient message size limit
  stored in Amavisd database (column `policy.message_size_limit`), reject email
  if message size exceeded.

## Plugins for OpenLDAP backend

* `ldap_maillist_access_policy`: restrict who can send email to mail list.
* `ldap_force_change_password_in_days`: force users to change password in days (default 90 days). User cannot send email before resetting password.
* Not used anymore: ~~ `ldap_amavisd_block_blacklisted_senders`: per-user sender whitelist and blacklist. ~~
* Not used anymore: ~~ `ldap_recipient_restrictions`: per-user recipient whitelist and blacklist. ~~

## Plugins for MySQL/MariaDB and PostgreSQL backends

* `sql_alias_access_policy`: restrict who can send email to mail alias.
* `sql_user_restrictions`: per-user sender and recipient restrictions.
* `sql_force_change_password_in_days`: force users to change password in days (default 90 days). User cannot send email before resetting password.

