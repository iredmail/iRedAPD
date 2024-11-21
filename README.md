# Project Overview
iRedAPD is a simple [Postfix policy server](http://www.postfix.org/SMTPD_POLICY_README.html), 
written in Python and runs as a low-privileged user (`iredapd` by default), with plugin support.

**Key Features:**
- Works with OpenLDAP, MySQL/MariaDB, and PostgreSQL backends.
- License: GPL v3 (with exceptions for certain files).
- Default listening ports:
    - `7777`: Normal SMTP policy service.
    - `7778`: Sender Rewriting Scheme (SRS) for sender address rewriting.
    - `7779`: SRS for recipient address rewriting.

**Notes:**
- Sub-project of the [iRedMail project](http://www.iredmail.org).
- Pre-installed and enabled in iRedMail by default.
- Can be managed via the iRedMail [web admin panel - iRedAdmin-Pro](http://www.iredmail.org/admin_panel.html).

## Prerequisites
- Python 3.5+

## Installation Steps
**Standard Installation:** Refer to the `INSTALL.md` document for detailed installation instructions.

## Manage iRedAPD with Command-Line Tools
Comprehensive documentation is available with detailed tutorial here: [Manage iRedAPD](http://www.iredmail.org/docs/manage.iredapd.html).

## Available Plugins
### For All Backends
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


### For OpenLDAP Backend
- `ldap_maillist_access_policy`: Restrict who can send emails to a mail list.
- `ldap_force_change_password_in_days`: Enforce password changes after a set period.

### For MySQL/MariaDB and PostgreSQL Backends
- `sql_alias_access_policy`: Restrict who can send emails to an alias.
- `sql_force_change_password_in_days`: Enforce password changes after a set period.

## External Documents
Refer to additional documents like `INSTALL.md` and `CONTRIBUTE.md` for comprehensive guides.

## Version History
Please refer to the [Change Log](ChangeLog) for details.

## Help and Support
For FAQs, common issues, and user interactions, refer to GitHub Issues and Pull Requests.



