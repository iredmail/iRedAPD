# Introduction

* iRedAPD is a simple [Postfix policy server](http://www.postfix.org/SMTPD_POLICY_README.html), written in Python, with plugin support.
* iRedAPD listens on port `7777`, runs as a low-privileged user (`iredapd` by default).
* The latest iRedAPD works with OpenLDAP, MySQL and PostgreSQL backends.
* License: GPL v3.
* Author: Zhang Huangbin <zhb _at_ iredmail.org>.

**NOTE**: 

* iRedAPD is a sub-project of [iRedMail project](http://www.iredmail.org).
* iRedAPD is installed and enabled in iRedMail by default, so you don’t need this tutorial if you already have iRedMail running.
* You can manage iRedAPD with iRedMail [web admin panel - iRedAdmin-Pro](http://www.iredmail.org/admin_panel.html).

## Available plugins:

Plugins are files placed under `plugins/` directory, plugin name is file name without file extension `.py`.

* For OpenLDAP backend:
	* `ldap_maillist_access_policy`: restrict who can send email to mail list.
	* `ldap_amavisd_block_blacklisted_senders`: per-user sender whitelist and blacklist.
	* `ldap_recipient_restrictions`: per-user recipient whitelist and blacklist.
	* `ldap_expired_password`: reject sender if his/her password was not changed in 90 days.
	* `ldap_domain_wblist`: per-domain whitelists and blacklists.

* For MySQL and PostgreSQL backends:
	* `sql_alias_access_policy`: restrict who can send email to mail alias.
	* `sql_user_restrictions`: per-user sender and recipient restrictions.

# Requirements

* `iRedMail`: All iRedMail versions should work as expected.
* `Python` >= 2.4: core programming language.
* `Python-LDAP` >= 2.3.7: API to access LDAP directory servers from Python programs. Required by OpenLDAP backend.
* `Python-MySQLdb` >= 1.2.2: Python DB API interface for MySQL database. Required by MySQL backend.
* `psycopg2` >= 2.4: Python DB API interface for PostgreSQL database. Required by PostgreSQL backend.

# Install iRedAPD

## Create a low privilege user as iRedAPD daemon user

It’s recommended to run iRedAPD as a low privilege user for security reason, let’s create user `iredapd` as daemon user.

* Create user on Red Hat, CentOS, Scientific Linux, Debian, Ubuntu, Gentoo, openSUSE, OpenBSD:

		# useradd -m -s /sbin/nologin -d /home/iredapd iredapd

* Create user on FreeBSD:

		# pw useradd -s /sbin/nologin -d /home/iredapd -n iredapd

## Install required packages

* On Red Hat, CentOS, Scientific Linux:

		# ---- For OpenLDAP backend:
		# yum install python-ldap MySQL-python
		
		# ---- For MySQL backend:
		# yum install MySQL-python
		
		# ---- For PostgreSQL backend:
		# yum install python-pyscopg2

* on Debian, Ubuntu:

		# —— For OpenLDAP backend:
		$ sudo apt-get install python-ldap python-mysqldb
		
		# —— For MySQL backend:
		$ sudo apt-get install python-mysqldb
		
		# —— For PostgreSQL backend:
		$ sudo apt-get install python-psycopg2

* on openSUSE:

		# ---- For OpenLDAP backend:
		# zypper install python-ldap python-mysql
		
		# ---- For MySQL backend:
		# yum install python-mysql
		
		# ---- For PostgreSQL backend:
		# yum install python-pyscopg2

* on Gentoo:

		# ---- For OpenLDAP backend:
		# emerge python-ldap mysql-python

		# ---- For MySQL backend:
		# emerge mysql-python

		# ---- For PostgreSQL backend:
		# emerge psycopg

* on FreeBSD:

		# ---- For OpenLDAP backend:
		# cd /usr/ports/net/py-ldap2 && make install clean
		# cd /usr/ports/databases/py-MySQLdb && make install clean

		# ---- For MySQL backend:
		# cd /usr/ports/databases/py-MySQLdb && make install clean

		# ---- For PostgreSQL backend:
		# cd /usr/ports/databases/py-psycopg2 && make install clean

* on OpenBSD:

		# ---- For OpenLDAP backend:
		# pkg_add -r py-ldap py-mysql

		# ---- For MySQL backend:
		# pkg_add -r py-mysql

		# ---- For PostgreSQL backend:
		# pkg_add -r py-psycopg2

## Download and configure iRedAPD

* Download the latest iRedAPD from project page: https://bitbucket.org/zhb/iredapd/downloads
* Extract iRedAPD to /opt/, set correct file permissions, and create symbol link.

		# tar xjf iRedAPD-x.y.z.tar.bz2 -C /opt/
		# ln -s /opt/iRedAPD-x.y.z /opt/iredapd
		# chown -R iredapd:iredapd /opt/iRedAPD-x.y.z/
		# chmod -R 0700 /opt/iRedAPD-x.y.z/

* Copy RC script to /etc/init.d/ (Linux) , /usr/local/etc/rc.d/ (FreeBSD), /etc/rc.d/ (OpenBSD), and set correct permission. **NOTE**: We have RC scripts for different Linux/BSD distributions, please copy the one for your distribution. e.g. `iredapd.rhel` for Red Hat, CentOS, Scientific Linux, `iredapd.debian` for Debian, Ubuntu.

		# cp /opt/iredapd/rc_scripts/iredapd.rhel /etc/init.d/iredapd
		# chmod +x /etc/init.d/iredapd

* Create a new config file by copying sample config. **WARNING**: config file contains LDAP/SQL username and password, please don't make it world readable.

		# cp /opt/iredapd/settings.py.sample /opt/iredapd/settings.py
		# chmod 0600 /opt/iredapd/settings.py

* Open /opt/iredapd/settings.py and set correct values:

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
		# - Plugin name is file name which placed under 'plugins/' directory,
		#   without file extension '.py'.
		# - Plugin names MUST be seperated by comma.
		plugins = ['ldap_maillist_access_policy', 'ldap_amavisd_block_blacklisted_senders']

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

* Create log file: `/var/log/iredapd.log`.

		# touch /var/log/iredapd.log

* Make iRedAPD start when boot your server.

		# ---- on RHEL/CentOS ----
		# chkconfig --level 345 iredapd on

		# ---- on Debian/Ubuntu ----
		$ sudo update-rc.d iredapd defaults

		# ---- on FreeBSD, please edit /etc/rc.conf, append below line ----
		iredapd_enable='YES'
		
		# —— on OpenBSD, please list service `iredapd` in parameter `pkg_scripts=` in file `/etc/rc.conf.local` ——
		pkg_scripts=“ ... iredapd”

* Start iRedAPD service:

		# —— on Linux ----
		# /etc/init.d/iredapd restart
		
		# —— on FreeBSD ——
		# /usr/local/etc/rc.d/iredapd restart

		# —— on OpenBSD ——
		# /etc/rc.d/iredapd restart

# Configure Postfix to use iRedAPD as policy server

* In Postfix config file `/etc/postfix/main.cf` (it’s `/usr/local/etc/postfix/main.cf` on FreeBSD), modify parameter `smtpd_recipient_restrictions =` to enable iRedAPD like below:

		smtpd_recipient_restrictions =
		    ...
		    check_policy_service inet:127.0.0.1:7777,     # <-- Insert this line before "permit_mynetworks"
		    permit_mynetworks,
		    permit_sasl_authenticated,
		    ...

**WARNING**: Order of restriction rules is very important, please make sure you have `check_policy_service inet:127.0.0.1:7777` before `permit_mynetworks`.

* Restart Postfix service to enable iRedAPD.

		# — on Linux
		# /etc/init.d/postfix restart
		
		# —— on FreeBSD
		# /usr/local/etc/rc.d/postfix restart
		
		# —— on OpenBSD
		# /etc/rc.d/postfix restart

# Rotate iRedAPD log file with logrotate

* on Linux, please add logrotate config file `/etc/logrotate.d/iredapd` to rotate iRedAPD log file:

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

* on FreeBSD, please append below line in `/etc/newsyslog.conf` to rotate iRedAPD log file:

		/var/log/iredapd.log    root:wheel   640  7     *    24    Z /var/run/iredapd.pid

* on OpenBSD, please append below line in `/etc/newsyslog.conf` to rotate iRedAPD log file:

		/var/log/iredapd.log    root:wheel   640  7     *    24    Z “/etc/rc.d/iredapd restart >/dev/null"

# Troubleshooting & Debug

If iRedAPD doesn't work as expected, you can simplily set log_level = debug in /opt/iredapd/etc/iredapd.ini, restart iredapd and monitor its log file /var/log/iredapd.log, create a new forum topic in iRedMail forum and paste log message in forum topic.

# FAQ

## Available access policies

Below access policies are recognized in iRedAPD-1.4.0 and later releases:

<table>
<tr><th>Restriction</th><th>Comment</th><th>Value of access policy</th></tr>
<tr><td>Unrestricted</td><td>Everyone can mail to this address</td><td>public</td></tr>
<tr><td>Domain Wide</td><td>Only users under same domain can send mail to this address</td><td>domain</td></tr>
<tr><td>Domain and all sub-domains	</td><td>Only users under same domain and sub-domains can send mail to this address</td><td>subdomain</td></tr>
<tr><td>Members Only</td><td>Only members can send mail to this address</td><td>membersOnly</td></tr>
<tr><td>Moderators Only</td><td>Only moderators can send mail to this address</td><td>allowedOnly</td></tr>
<tr><td>Moderators Only</td><td>Only members and moderators can send mail to this address</td><td>membersAndModeratorsOnly</td></tr>
</table>

**NOTE**:

* For OpenLDAP backend, value of access policy is stored in LDAP attribute `accessPolicy` of mail list object.
* For MySQL or PostgreSQL backend, value of access policy is stored in SQL column `alias.accesspolicy`.

## [SQL backend] How to add moderators for mail alias

To add moderators for certain mail alias, just list all email addresses of moderators in SQL column `alias.moderators`, multiple addresses must be separated by comma. For example:

		sql> UPDATE alias SET moderators='user1@domain.ltd' WHERE address='myalias01@domain.ltd';
		sql> UPDATE alias SET moderators='user1@domain.ltd,user2@domain.ltd,user3@domain.ltd' WHERE address='myalias02@domain.ltd';

