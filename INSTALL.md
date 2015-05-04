# Installation Requirements

* `iRedMail`: All iRedMail versions should work as expected.
* `Python` >= 2.4: core programming language.
* `SQLAlchemy` >= 0.9: The Python SQL Toolkit and Object Relational Mapper.
  iRedAPD just uses its sql connection pool, not ORM.
* `Python-LDAP` >= 2.3.7: API to access LDAP directory servers from Python
  programs. Required by OpenLDAP backend.
* `Python-MySQLdb` >= 1.2.2: Python DB API interface for MySQL database.
  Required by OpenLDAP and MySQL backend.
* `psycopg2` >= 2.4: Python DB API interface for PostgreSQL database.
  Required by PostgreSQL backend.

# Install iRedAPD

## Create a low privilege user as iRedAPD daemon user

It’s recommended to run iRedAPD as a low privilege user for security reason, let’s create user `iredapd` as daemon user.

* Create user on Red Hat, CentOS, Scientific Linux, Debian, Ubuntu, Gentoo, openSUSE, OpenBSD:

```shell
# useradd -m -s /sbin/nologin -d /home/iredapd iredapd
```

* Create user on FreeBSD:

```
# pw useradd -s /sbin/nologin -d /home/iredapd -n iredapd
```

## Install required packages

* On Red Hat, CentOS, Scientific Linux:

```shell
# ---- For OpenLDAP backend:
# yum install python-ldap MySQL-python python-sqlalchemy

# ---- For MySQL backend:
# yum install MySQL-python python-sqlalchemy

# ---- For PostgreSQL backend:
# yum install python-pyscopg2 python-sqlalchemy
```

* on Debian, Ubuntu:

```shell
# —— For OpenLDAP backend:
$ sudo apt-get install python-ldap python-mysqldb python-sqlalchemy

# —— For MySQL backend:
$ sudo apt-get install python-mysqldb python-sqlalchemy

# —— For PostgreSQL backend:
$ sudo apt-get install python-psycopg2 python-sqlalchemy
```

* on FreeBSD:

```shell
# ---- For OpenLDAP backend:
# cd /usr/ports/net/py-ldap2 && make install clean
# cd /usr/ports/databases/py-MySQLdb && make install clean
# cd /usr/ports/databases/py-sqlalchemy && make install clean

# ---- For MySQL backend:
# cd /usr/ports/databases/py-MySQLdb && make install clean
# cd /usr/ports/databases/py-sqlalchemy && make install clean

# ---- For PostgreSQL backend:
# cd /usr/ports/databases/py-psycopg2 && make install clean
# cd /usr/ports/databases/py-sqlalchemy && make install clean
```

* on OpenBSD:

```
# ---- For OpenLDAP backend:
# pkg_add -r py-ldap py-mysql py-sqlalchemy

# ---- For MySQL backend:
# pkg_add -r py-mysql py-mysql py-sqlalchemy

# ---- For PostgreSQL backend:
# pkg_add -r py-psycopg2 py-mysql py-sqlalchemy
```

## Download and configure iRedAPD

* Download the latest iRedAPD from project page: [https://bitbucket.org/zhb/iredapd/downloads](https://bitbucket.org/zhb/iredapd/downloads).
* Extract iRedAPD to /opt/, set correct file permissions, and create symbol link.

```shell
# tar xjf iRedAPD-x.y.z.tar.bz2 -C /opt/
# ln -s /opt/iRedAPD-x.y.z /opt/iredapd
# chown -R iredapd:iredapd /opt/iRedAPD-x.y.z/
# chmod -R 0700 /opt/iRedAPD-x.y.z/
```

* Copy RC script to /etc/init.d/ (Linux) , /usr/local/etc/rc.d/ (FreeBSD), /etc/rc.d/ (OpenBSD), and set correct permission. **NOTE**: We have RC scripts for different Linux/BSD distributions, please copy the one for your distribution. e.g. `iredapd.rhel` for Red Hat, CentOS, Scientific Linux, `iredapd.debian` for Debian, Ubuntu.

```shell
# cp /opt/iredapd/rc_scripts/iredapd.rhel /etc/init.d/iredapd
# chmod +x /etc/init.d/iredapd
```

* Create a new config file by copying sample config. **WARNING**: config file contains LDAP/SQL username and password, please don't make it world readable.

```shell
# cp /opt/iredapd/settings.py.sample /opt/iredapd/settings.py
# chmod 0600 /opt/iredapd/settings.py
```

* Open /opt/iredapd/settings.py and set correct values:

```python
# Listen address and port.
listen_address = "127.0.0.1"
listen_port = "7777"

# Daemon user.
run_as_user = "iredapd"

# Path to pid file.
pid_file = "/var/run/iredapd.pid"

# Log file.
log_file = "/var/log/iredapd.log"

# Log level: info, warning, error, debug.
# 'info' is recommended for product use.
log_level = "info"

# Backend: ldap, mysql, pgsql.
backend = "ldap"

# Enabled plugins.
plugins = ['reject_null_sender', 'ldap_maillist_access_policy', 'ldap_amavisd_block_blacklisted_senders']

# For OpenLDAP backend. Not used by MySQL and PostgreSQL backends.
ldap_uri = “ldap://127.0.0.1:389”
ldap_basedn = “o=domains,dc=iredmail,dc=org”
ldap_binddn = “cn=vmail,dc=iredmail,dc=org”
ldap_bindpw = “mRAEWpGRtlCs1O0QuWpXoaJ36EjRql”

# For MySQL and PostgreSQL backends. Not used by OpenLDAP backend.
sql_server = "127.0.0.1"
sql_db = "vmail"
sql_user = "vmail"
sql_password = "Psaf68wsuVctYSbj4PJzRqmFsE0rlQ"
```

* Create log file: `/var/log/iredapd.log`.

```shell
# touch /var/log/iredapd.log
```

* Make iRedAPD start when boot your server.

```shell
# ---- on RHEL/CentOS ----
# chkconfig --level 345 iredapd on

# ---- on Debian/Ubuntu ----
$ sudo update-rc.d iredapd defaults

# ---- on FreeBSD, please edit /etc/rc.conf, append below line ----
iredapd_enable='YES'
		
# —— on OpenBSD, please list service `iredapd` in parameter `pkg_scripts=` in file `/etc/rc.conf.local` ——
pkg_scripts=“ ... iredapd”
```

* Start iRedAPD service:

```shell
# —— on Linux ----
# /etc/init.d/iredapd restart
		
# —— on FreeBSD ——
# /usr/local/etc/rc.d/iredapd restart

# —— on OpenBSD ——
# /etc/rc.d/iredapd restart
```

# Configure Postfix to use iRedAPD as policy server

In Postfix config file `/etc/postfix/main.cf` (it’s
`/usr/local/etc/postfix/main.cf` on FreeBSD), modify parameter
`smtpd_recipient_restrictions =` to enable iRedAPD like below:

```
smtpd_recipient_restrictions =
    ...
    check_policy_service inet:127.0.0.1:7777,  # <-- Insert this line before "permit_mynetworks"
    permit_mynetworks,
    permit_sasl_authenticated,
    ...
```

**WARNING**: Order of restriction rules is very important, please make sure
you have `check_policy_service inet:127.0.0.1:7777` before `permit_mynetworks`.

Restart Postfix service to enable iRedAPD.

```shell
# — on Linux
# /etc/init.d/postfix restart
		
# —— on FreeBSD
# /usr/local/etc/rc.d/postfix restart
		
# —— on OpenBSD
# /etc/rc.d/postfix restart
```

Since iRedAPD-`1.4.4`, it works with Postfix parameter
`smtpd_end_of_data_restrictions`. So if you need plugins which should be
applied in smtp protocol state `END-OF-MESSAGE`, please enable iRedAPD like
below:

```
smtpd_end_of_data_restrictions = check_policy_service inet:127.0.0.1:7777
```

# Rotate iRedAPD log file with logrotate

* on Linux, please add logrotate config file `/etc/logrotate.d/iredapd` to rotate iRedAPD log file:

```
/var/log/iredapd.log {
    compress
    daily
    rotate 30
    missingok

    # Use bzip2 for compress.
    compresscmd /usr/bin/bzip2
    uncompresscmd /usr/bin/bunzip2
    compressoptions -9
    compressext .bz2 

    # Used on RHEL/CentOS.
    postrotate
        /bin/kill -HUP $(cat /var/run/syslogd.pid 2> /dev/null) 2> /dev/null || true
    endscript

    # Used on Ubuntu.
    #postrotate
    #    invoke-rc.d sysklogd reload > /dev/null
    #endscript
}
```

* on FreeBSD, please append below line in `/etc/newsyslog.conf` to rotate iRedAPD log file:

```
/var/log/iredapd.log    root:wheel   640  7     *    24    Z /var/run/iredapd.pid
```

* on OpenBSD, please append below line in `/etc/newsyslog.conf` to rotate iRedAPD log file:

```
/var/log/iredapd.log    root:wheel   640  7     *    24    Z “/etc/rc.d/iredapd restart >/dev/null"
```

# Troubleshooting & Debug

If iRedAPD doesn't work as expected, please set `log_level = debug` in its
config file `/opt/iredapd/settings.py`, restart iredapd and reproduce your
issue. Then create a new forum topic in iRedMail
[online support forum](http://www.iredmail.org/forum/), extract issue
related log from log file `/var/log/iredapd.log`, then post log in your forum
post.

# FAQ

## Available access policies

Below access policies are recognized in iRedAPD-1.4.0 and later releases:

* `public`:  Unrestricted. Everyone can mail to this address.
* `domain`: Only users under same domain can send mail to this address.
* `subdomain`: Only users under same domain and sub-domains can send mail to this address.
* `membersOnly`: Only members can send mail to this address.
* `allowedOnly`: Only moderators can send mail to this address.
* `membersAndModeratorsOnly`: Only members and moderators can send mail to this address.

**NOTE**:

* For OpenLDAP backend, value of access policy is stored in LDAP attribute `accessPolicy` of mail list object.
* For MySQL or PostgreSQL backend, value of access policy is stored in SQL column `alias.accesspolicy`.

## [SQL backend] How to add moderators for mail alias

To add moderators for certain mail alias, just list all email addresses of moderators in SQL column `alias.moderators`, multiple addresses must be separated by comma. For example:

```sql
sql> UPDATE alias SET moderators='user1@domain.ltd' WHERE address='myalias01@domain.ltd';
sql> UPDATE alias SET moderators='user1@domain.ltd,user2@domain.ltd,user3@domain.ltd' WHERE address='myalias02@domain.ltd';
```


