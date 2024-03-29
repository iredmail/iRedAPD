# Installation Requirements

* `iRedMail`: All iRedMail versions should work as expected.
* `Python` >= 2.4: core programming language.
* `web.py` >= 0.39: utility used to parse URI.
* `SQLAlchemy` >= 0.9: The Python SQL Toolkit and Object Relational Mapper.
* `Python-LDAP` >= 2.3.7: API to access LDAP directory servers from Python
  programs. Required by OpenLDAP backend.
* `Python-MySQLdb` >= 1.2.2: Python DB API interface for MySQL database.
  Required by OpenLDAP and MySQL backend.
* `psycopg2` >= 2.4: Python DB API interface for PostgreSQL database.
  Required by PostgreSQL backend.

# Install iRedAPD

## Create a low privilege user as iRedAPD daemon user

It’s recommended to run iRedAPD as a low privilege user for security reason,
we will create user/group `iredapd` as daemon user.

* Create user on Red Hat, CentOS, Debian, Ubuntu, OpenBSD:

```shell
# useradd -m -s /sbin/nologin -d /home/iredapd iredapd
```

* Create user on FreeBSD:

```
# pw useradd -s /sbin/nologin -d /home/iredapd -n iredapd
```

## Install required packages

* On Red Hat, CentOS:

```shell
# ---- For OpenLDAP backend:
# yum install python-ldap MySQL-python python-sqlalchemy
# easy_install web.py

# ---- For MySQL backend:
# yum install MySQL-python python-sqlalchemy
# easy_install web.py

# ---- For PostgreSQL backend:
# yum install python-pyscopg2 python-sqlalchemy
# easy_install web.py
```

* on Debian, Ubuntu:

```shell
# —— For OpenLDAP backend:
$ sudo apt-get install python-ldap python-mysqldb python-sqlalchemy python-webpy

# —— For MySQL backend:
$ sudo apt-get install python-mysqldb python-sqlalchemy python-webpy

# —— For PostgreSQL backend:
$ sudo apt-get install python-psycopg2 python-sqlalchemy python-webpy
```

* on FreeBSD:

```shell
# ---- For OpenLDAP backend:
# cd /usr/ports/net/py-ldap2 && make install clean
# cd /usr/ports/databases/py-MySQLdb && make install clean
# cd /usr/ports/databases/py-sqlalchemy && make install clean
# cd /usr/ports/www/webpy && make install clean

# ---- For MySQL backend:
# cd /usr/ports/databases/py-MySQLdb && make install clean
# cd /usr/ports/databases/py-sqlalchemy && make install clean
# cd /usr/ports/www/webpy && make install clean

# ---- For PostgreSQL backend:
# cd /usr/ports/databases/py-psycopg2 && make install clean
# cd /usr/ports/databases/py-sqlalchemy && make install clean
# cd /usr/ports/www/webpy && make install clean
```

* on OpenBSD:

```
# ---- For OpenLDAP backend:
# pkg_add -r py-ldap py-mysql py-sqlalchemy py-webpy

# ---- For MySQL backend:
# pkg_add -r py-mysql py-mysql py-sqlalchemy py-webpy

# ---- For PostgreSQL backend:
# pkg_add -r py-psycopg2 py-mysql py-sqlalchemy py-webpy
```

## Download and configure iRedAPD

* Download the latest iRedAPD from project page: [https://bitbucket.org/zhb/iredapd/downloads](https://bitbucket.org/zhb/iredapd/downloads).
* Extract iRedAPD to `/opt/`, set correct file permissions, and create symbol link.

```shell
# tar xjf iRedAPD-x.y.z.tar.bz2 -C /opt/
# ln -s /opt/iRedAPD-x.y.z /opt/iredapd
# chown -R root:root /opt/iRedAPD-x.y.z/
# chmod -R 0500 /opt/iRedAPD-x.y.z/
```

* Copy RC script to `/etc/init.d/` (Linux), or `/usr/local/etc/rc.d/`
  (FreeBSD), `/etc/rc.d/` (OpenBSD), and set correct permission.

    * `iredapd.rhel` for Red Hat, CentOS.
    * `iredapd.debian` for Debian, Ubuntu.

```shell
# cp /opt/iredapd/rc_scripts/iredapd.rhel /etc/init.d/iredapd
# chmod +x /etc/init.d/iredapd
```

* Create a new config file by copying sample config.

    __WARNING__: Config file contains SQL/LDAP username and password, please
    don't make it world-readable.

```shell
# cp /opt/iredapd/settings.py.sample /opt/iredapd/settings.py
# chown root:root /opt/iredapd/settings.py
# chmod 0400 /opt/iredapd/settings.py
```

* Open `/opt/iredapd/settings.py` and set correct values:

    iRedAPD will listen on 3 network ports by default:

    - `7777`: for general smtp access policy, greylisting, throttling, etc.
    - `7778`: for (SRS) sender address rewriting
    - `7779`: for (SRS) recipient address rewriting

```python
# Listen address and port.
listen_address = "127.0.0.1"
listen_port = "7777"
srs_forward_port = "7778"
srs_reverse_port = "7779"

# Daemon user.
run_as_user = "iredapd"

# Path to pid file.
pid_file = "/var/run/iredapd.pid"

# Log level: info, warning, error, debug.
# 'info' is recommended for product use.
log_level = "info"

# Backend: ldap, mysql, pgsql.
backend = "ldap"

# Enabled plugins.
plugins = ['reject_null_sender', 'amavisd_wblist', 'ldap_maillist_access_policy']

srs_domain = 'my.full.hostname'
srs_secrets = ['7d86deed2cdee17baa8cf216348efe05']

# For OpenLDAP backend. Not used by MySQL and PostgreSQL backends.
ldap_uri = "ldap://127.0.0.1:389"
ldap_basedn = "o=domains,dc=iredmail,dc=org"
ldap_binddn = "cn=vmail,dc=iredmail,dc=org"
ldap_bindpw = "mRAEWpGRtlCs1O0QuWpXoaJ36EjRql"

# For MySQL and PostgreSQL backends. Not used by OpenLDAP backend.
sql_server = "127.0.0.1"
sql_db = "vmail"
sql_user = "vmail"
sql_password = "Psaf68wsuVctYSbj4PJzRqmFsE0rlQ"
```

* Create log file: `/var/log/iredapd/iredapd.log`.

```shell
mkdir -p /var/log/iredapd
touch /var/log/iredapd/iredapd.log
chown -R iredapd:iredapd /var/log/iredapd
```

* Copy `/opt/iredapd/samples/rsyslog.d/iredapd.conf` to `/etc/rsyslog.d/` and restart rsyslog service

```shell
# —— on Linux ----
cp /opt/iredapd/samples/rsyslog.d/iredapd.conf /etc/rsyslog.d/
chown root:root /etc/rsyslog.d/iredapd.conf
service rsyslog restart
```

* Optional: To enable logrotate, copy `/opt/iredapd/samples/logrotate.d/iredapd` to `/etc/logrotate.d/` and restart logrotate service 

```shell
# —— on Linux ----
cp /opt/iredapd/samples/logrotate.d/iredapd /etc/logrotate.d/
service logrotate restart
```

* Run command `crontab -e -u root` to add cron jobs for root user:

```
# iRedAPD: Clean up database hourly.
1   *   *   *   *   python /opt/iredapd/tools/cleanup_db.py >/dev/null

# iRedAPD: Convert SPF DNS record of specified domain names to IP
#          addresses/networks hourly.
2   *   *   *   *   python /opt/iredapd/tools/spf_to_greylist_whitelists.py >/dev/null
```

* Enable iRedAPD service:

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

# Configure Postfix to use iRedAPD as SMTP policy server

Note: Restarting Postfix service is required after you modified its config
files (`/etc/postfix/main.cf` and `/etc/postfix/master.cf`).

## Use iRedAPD as SMTP policy server

In Postfix config file `/etc/postfix/main.cf` (it’s
`/usr/local/etc/postfix/main.cf` on FreeBSD), update parameter
`smtpd_recipient_restrictions` and `smtpd_end_of_data_restrictions` like below
to enable iRedAPD:

```
smtpd_recipient_restrictions =
    ...
    check_policy_service inet:127.0.0.1:7777,
    permit_mynetworks,
    ...

smtpd_end_of_data_restrictions =
    check_policy_service inet:127.0.0.1:7777
```

**WARNING**:

* Order of restriction rules is very important, please make sure you have
  `check_policy_service inet:127.0.0.1:7777` before `permit_mynetworks`.
* If you update Postfix `mynetworks=` with some IP addresses/networks, please
  also list them in iRedAPD config file `/opt/iredapd/settings.py`, parameter
  `MYNETWORKS =`.

## [OPTIONAL] Use iRedAPD as SRS (Sender Rewriting Scheme) policy server

In Postfix config file `/etc/postfix/main.cf` (it’s
`/usr/local/etc/postfix/main.cf` on FreeBSD), add 4 new parameters:

```
sender_canonical_maps = tcp:127.0.0.1:7778
sender_canonical_classes = envelope_sender
recipient_canonical_maps = tcp:127.0.0.1:7779
recipient_canonical_classes= envelope_recipient,header_recipient
```

## Restart Postfix service to enable iRedAPD

```shell
# -- on Linux and FreeBSD
# service postfix restart

# -- on OpenBSD
# rcctl restart postfix
```

# Rotate iRedAPD log file with logrotate

* on Linux, please add logrotate config file `/etc/logrotate.d/iredapd` to rotate iRedAPD log file:

```
/var/log/iredapd/iredapd.log {
    compress
    delaycompress
    daily
    rotate 30
    missingok

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
/var/log/iredapd/iredapd.log    root:wheel   640  7     *    24    Z /var/run/iredapd.pid
```

* on OpenBSD, please append below line in `/etc/newsyslog.conf` to rotate iRedAPD log file:

```
/var/log/iredapd/iredapd.log    root:wheel   640  7     *    24    Z “/etc/rc.d/iredapd restart >/dev/null"
```

# Troubleshooting & Debug

If iRedAPD doesn't work as expected, please set `log_level = debug` in its
config file `/opt/iredapd/settings.py`, restart iredapd and reproduce your
issue. Then create a new forum topic in iRedMail
[online support forum](http://www.iredmail.org/forum/), extract issue
related log from log file `/var/log/iredapd.log`, then post log in your forum
post.

# FAQ

## Available access policies for mail alias and mailing list

Below access policies are recognized in iRedAPD-1.4.0 and later releases:

    * For OpenLDAP backend, access policy is stored in attribute `accessPolicy`
      of mailing list account.
    * For MySQL or PostgreSQL backends, access policy is stored in SQL column
      `alias.accesspolicy` (mail alias account) or `maillists.accesspolicy`
      (mailing list account).

* `public`:  Unrestricted. Everyone can mail to this address.
* `domain`: Only users under same domain can send mail to this address.
* `subdomain`: Only users under same domain and sub-domains can send mail to this address.
* `membersonly`: Only members can send mail to this address.
* `moderatorsonly`: Only moderators can send mail to this address.
* `membersandmoderatorsonly`: Only members and moderators can send mail to this address.


## [SQL backend] How to add moderators for mail alias

To add moderators for certain mail alias, just list all email addresses of moderators in SQL column `alias.moderators`, multiple addresses must be separated by comma. For example:

```sql
sql> UPDATE alias SET moderators='user1@domain.ltd' WHERE address='myalias01@domain.ltd';
sql> UPDATE alias SET moderators='user1@domain.ltd,user2@domain.ltd,user3@domain.ltd' WHERE address='myalias02@domain.ltd';
```
