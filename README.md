
# About

* iRedAPD is a simple Postfix policy server.
* iRedAPD is a part of iRedMail project. http://www.iredmail.org/

# Authors & Contributors

* Zhang Huangbin <zhb @ iredmail.org>: Core developer and maintainer.

# License

iRedAPD is based on [mlapd](http://code.google.com/p/mlapd) which released
under GPL v2, so iRedAPD is GPL v2 too.

Note: file src/daemon.py is released under its own license, shipped
for easy deploying.

# Requirments

* [Python](http://www.python.org/) >= 2.4
* [python-ldap](http://python-ldap.org/) >= 2.2.0. Required for OpenLDAP backend
* [python-mysql](http://mysql-python.sourceforge.net/) >= 1.2.0. Required for MySQL backend.
* [python-psycopg2](http://initd.org/) >= 2.1.0. Required for PostgreSQL backend.

# Document

* [Install iRedAPD for OpenLDAP backend](http://www.iredmail.org/wiki/index.php?title=Install/iRedAPD/OpenLDAP)
* [Install iRedAPD for MySQL backend](http://www.iredmail.org/wiki/index.php?title=Install/iRedAPD/MySQL)

* [iRedMail documentations](http://www.iredmail.org/doc.html)
* [Postfix SMTP Access Policy Delegation](http://www.postfix.org/SMTPD_POLICY_README.html)
