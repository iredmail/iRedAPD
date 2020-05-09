# Introduction

* iRedAPD is a simple [Postfix policy server](http://www.postfix.org/SMTPD_POLICY_README.html),
  written in Python and runs as a low-privileged user (`iredapd` by default),
  with plugin support.
* The latest iRedAPD works with OpenLDAP, MySQL/MariaDB and PostgreSQL backends.
* __License: GPL v3__, except few files are in different licenses, shipped in
  iRedAPD for easier setup, but not license change.
    * file `libs/daemon.py` is BSD license.
    * file `libs/srslib.py` is Apache License, Version 2.0.
* Author: Zhang Huangbin <zhb _at_ iredmail.org>.

**NOTES**:

* iRedAPD is a sub-project of [iRedMail project](http://www.iredmail.org).
* iRedAPD is installed and enabled in iRedMail by default, you don’t need
  this tutorial if you already have iRedMail running. For standard installation
  please check document `INSTALL.md`.
* iRedAPD listens on 3 ports by default:
    - `7777`: normal smtp policy service
    - `7778`: SRS (Sender Rewriting Scheme) for sender address rewriting
    - `7779`: SRS (Sender Rewriting Scheme) for recipient address rewriting
* You can manage iRedAPD with iRedMail [web admin panel - iRedAdmin-Pro](http://www.iredmail.org/admin_panel.html).

# Requirements

- Python 3.5+

# Manage iRedAPD with command line tools

iRedMail project has a detailed tutorial to show you how to manage iRedAPD
with command line tools: [Manage iRedAPD](http://www.iredmail.org/docs/manage.iredapd.html)

# Available plugins

Plugins are files placed under `plugins/` directory, plugin name is file name
without file extension `.py`. It's recommended to read comment lines in plugin
source files to understand how it works and what it does.

## Plugins for all backends

* `reject_to_hostname`: reject emails sent to `xxx@<server hostname>` from
  external network.
* `reject_sender_login_mismatch`: Reject sender login mismatch (addresses in
  `From:` and SASL username). It will verify user alias addresses against
  SQL/LDAP database.

    This plugin also verifies forged sender address, e.g. sending email as
    a local domain to local domain.

* `reject_null_sender`: Reject message submitted by sasl authenticated user but
  use null sender in `From:` header (`from=<>` in Postfix log).
  RECOMMENDED to enable this plugin. It doesn't require SQL/LDAP query.

    If your user's password was cracked by spammer, spammer can use
    this account to bypass smtp authentication, but with a null sender
    in `From:` header, throttling won't be triggered.

* `amavisd_wblist`: Whitelist/blacklist for both inbound and outbound messages.

    The white/blacklists are used by both iRedAPD (before-queue) and Amavisd
    (after-queue).

* `greylisting`: for greylisting service.
* `throttle`: Throttling based on:
    * max number of mail messages sent/received in specified period of time
    * total mail size sent in specified period of time
    * size of single message

* `whitelist_outbound_recipient`: automatically whitelist recipient addresses
  of outgoing emails sent by sasl authenticated (local) users. It's able to
  whitelist single recipient address or domain for greylisting and normal
  white/blacklist.

## Plugins for OpenLDAP backend

* `ldap_maillist_access_policy`: restrict who can send email to mail list.
* `ldap_force_change_password_in_days`: force users to change password in days (default 90 days). User cannot send email before resetting password.

## Plugins for MySQL/MariaDB and PostgreSQL backends

* `sql_alias_access_policy`: restrict who can send email to mail alias.
* `sql_force_change_password_in_days`: force users to change password in days (default 90 days). User cannot send email before resetting password.
