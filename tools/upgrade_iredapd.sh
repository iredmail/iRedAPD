#!/usr/bin/env bash
# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Upgrade iRedAPD from old release.

# USAGE:
#
#   * Download the latest iRedAPD from iRedMail web site.
#     http://www.iredmail.org/yum/misc/
#
#   * Extract downloaded iRedAPD
#   * Enter 'tools/' directory and execute script 'upgrade_iredapd.sh' as
#     root user:
#
#       # cd /opt/iRedAPD-xxx/tools/
#       # bash upgrade_iredapd.sh

export SYS_ROOT_USER='root'
export SYS_ROOT_GROUP='root'

export IREDAPD_DAEMON_USER='iredapd'
export IREDAPD_DAEMON_GROUP='iredapd'
export IREDAPD_LOG_DIR='/var/log/iredapd'
export IREDAPD_LOG_FILE="${IREDAPD_LOG_DIR}/iredapd.log"

# PostgreSQL system user.
export PGSQL_SYS_USER='postgres'
export PGSQL_SYS_GROUP='postgres'

# Check OS to detect some necessary info.
export KERNEL_NAME="$(uname -s | tr '[a-z]' '[A-Z]')"
export RC_SCRIPT_NAME='iredapd'

# Path to some programs.
export PYTHON_BIN='/usr/bin/python'
export MD5_BIN='md5sum'

if [ X"${KERNEL_NAME}" == X'LINUX' ]; then
    export DIR_RC_SCRIPTS='/etc/init.d'
    if [ -f /etc/redhat-release ]; then
        # RHEL/CentOS
        export DISTRO='RHEL'
        export IREDADMIN_CONF_PY='/var/www/iredadmin/settings.py'
        export CRON_SPOOL_DIR='/var/spool/cron'
    elif [ -f /etc/lsb-release ]; then
        # Ubuntu
        export DISTRO='UBUNTU'
        if [ -f '/usr/share/apache2/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/usr/share/apache2/iredadmin/settings.py'
        elif [ -f '/opt/www/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/opt/www/iredadmin/settings.py'
        fi
        export CRON_SPOOL_DIR='/var/spool/cron/crontabs'
    elif [ -f /etc/debian_version ]; then
        # Debian
        export DISTRO='DEBIAN'
        if [ -f '/usr/share/apache2/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/usr/share/apache2/iredadmin/settings.py'
        elif [ -f '/opt/www/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/opt/www/iredadmin/settings.py'
        fi
        export CRON_SPOOL_DIR='/var/spool/cron/crontabs'
    elif [ -f /etc/SuSE-release ]; then
        # openSUSE
        export DISTRO='SUSE'
        export IREDADMIN_CONF_PY='/srv/www/iredadmin/settings.py'
        export CRON_SPOOL_DIR='/var/spool/cron'
    else
        echo "<<< ERROR >>> Cannot detect Linux distribution name. Exit."
        echo "Please contact support@iredmail.org to solve it."
        exit 255
    fi
elif [ X"${KERNEL_NAME}" == X'FREEBSD' ]; then
    export DISTRO='FREEBSD'
    export SYS_ROOT_GROUP='wheel'
    export PGSQL_SYS_USER='pgsql'
    export DIR_RC_SCRIPTS='/usr/local/etc/rc.d'
    export IREDADMIN_CONF_PY='/usr/local/www/iredadmin/settings.py'
    export CRON_SPOOL_DIR='/var/cron/tabs'
    export PYTHON_BIN='/usr/local/bin/python'
    export MD5_BIN='md5'
elif [ X"${KERNEL_NAME}" == X'OPENBSD' ]; then
    export DISTRO='OPENBSD'
    export SYS_ROOT_GROUP='wheel'
    export PGSQL_SYS_USER='_postgresql'
    export DIR_RC_SCRIPTS='/etc/rc.d'
    export IREDADMIN_CONF_PY='/var/www/iredadmin/settings.py'
    export CRON_SPOOL_DIR='/var/cron/tabs'
    export PYTHON_BIN='/usr/local/bin/python'
    export MD5_BIN='md5'
else
    echo "Cannot detect Linux/BSD distribution. Exit."
    echo "Please contact author iRedMail team <support@iredmail.org> to solve it."
    exit 255
fi

echo "* Detected Linux/BSD distribution: ${DISTRO}"

# iRedAPD directory and config file.
export IREDAPD_ROOT_DIR="/opt/iredapd"
export IREDAPD_CONF_PY="${IREDAPD_ROOT_DIR}/settings.py"
export IREDAPD_CONF_INI="${IREDAPD_ROOT_DIR}/settings.ini"

if [ -L ${IREDAPD_ROOT_DIR} ]; then
    export IREDAPD_ROOT_REAL_DIR="$(readlink ${IREDAPD_ROOT_DIR})"
    echo "* Found iRedAPD directory: ${IREDAPD_ROOT_DIR}, symbol link of ${IREDAPD_ROOT_REAL_DIR}"
else
    echo "<<< ERROR >>> Directory is not a symbol link created by iRedMail. Exit."
    exit 255
fi

# Remove all single quote and double quotes in string.
strip_quotes()
{
    # Read input from stdin
    str="$(cat <&0)"

    value="$(echo ${str} | tr -d '"' | tr -d "'")"

    echo "${value}"
}

get_value_of_iredapd_setting()
{
    var="${1}"
    value="$(grep "^${var}" ${IREDAPD_CONF_PY} | awk '{print $NF}' | strip_quotes)"

    echo "${value}"
}

install_pkg()
{
    echo "Install package: $@"

    if [ X"${DISTRO}" == X'RHEL' ]; then
        yum -y install $@
    elif [ X"${DISTRO}" == X'DEBIAN' -o X"${DISTRO}" == X'UBUNTU' ]; then
        apt-get install -y --force-yes $@
    elif [ X"${DISTRO}" == X'FREEBSD' ]; then
        cd /usr/ports/$@ && make install clean
    elif [ X"${DISTRO}" == X'OPENBSD' ]; then
        pkg_add -r $@
    else
        echo "<< ERROR >> Please install package(s) manually: $@"
    fi
}

has_python_module()
{
    for mod in $@; do
        python -c "import $mod" &>/dev/null
        if [ X"$?" == X'0' ]; then
            echo 'YES'
        else
            echo 'NO'
        fi
    done
}

add_missing_parameter()
{
    # Usage: add_missing_parameter VARIABLE DEFAULT_VALUE [COMMENT]
    var="${1}"
    value="${2}"
    shift 2
    comment="$@"

    if ! grep "^${var}" ${IREDAPD_CONF_PY} &>/dev/null; then
        if [ ! -z "${comment}" ]; then
            echo "# ${comment}" >> ${IREDAPD_CONF_PY}
        fi

        if [ X"${value}" == X'True' -o X"${value}" == X'False' ]; then
            echo "${var} = ${value}" >> ${IREDAPD_CONF_PY}
        elif echo ${value} | grep '^[\[|\(]' &>/dev/null; then
            # Value is a list or tuple in Python format.
            echo "${var} = ${value}" >> ${IREDAPD_CONF_PY}
        else
            # Value must be quoted as string.
            echo "${var} = '${value}'" >> ${IREDAPD_CONF_PY}
        fi
    fi
}

# Copy config file
if [ -f ${IREDAPD_CONF_PY} ]; then
    echo "* Found iRedAPD config file: ${IREDAPD_CONF_PY}"
elif [ -f ${IREDAPD_CONF_INI} ]; then
    echo "* Found old iRedAPD config file: ${IREDAPD_CONF_INI}, please convert it"
    echo "  to new config format manually."
    exit 255
else
    echo "<<< ERROR >>> Cannot find valid config file (${IRA_CONF_PY})."
    exit 255
fi

# Check whether current directory is iRedAPD
export PWD="$(pwd)"
if ! echo ${PWD} | grep 'iRedAPD.*/tools' >/dev/null; then
    echo "<<< ERROR >>> Cannot find new version of iRedAPD in current directory. Exit."
    exit 255
fi

#
# Require SQL root password to create `iredapd` database.
#
export IREDAPD_DB_SERVER='127.0.0.1'
export IREDAPD_DB_USER='iredapd'
export IREDAPD_DB_NAME='iredapd'
export IREDAPD_DB_PASSWD="$(echo $RANDOM | ${MD5_BIN} | awk '{print $1}')"
if ! grep '^iredapd_db_' ${IREDAPD_CONF_PY} &>/dev/null; then

    # Check backend.
    if egrep '^backend.*(mysql|ldap)' ${IREDAPD_CONF_PY} &>/dev/null; then
        export IREDAPD_DB_PORT='3306'

        echo "Looks like you don't have 'iredapd' SQL database, please type root"
        echo "username and password of your SQL server to create it now."
        while :; do
            echo -n "MySQL root username: "
            read _sql_root_username

            echo -n "MySQL root password: "
            read _sql_root_password

            # Verify username and password
            mysql -u${_sql_root_username} -p${_sql_root_password} -e "show databases" >/dev/null
            if [ X"$?" == X'0' ]; then
                export _sql_root_username _sql_root_password
                break
            else
                echo "Username or password is wrong, please try again."
            fi
        done

        cp -f ${PWD}/../SQL/{iredapd.mysql,greylisting_whitelists.sql} /tmp/
        chmod 0555 /tmp/{iredapd.mysql,greylisting_whitelists.sql}

        # Create database and tables.
        mysql -u${_sql_root_username} -p${_sql_root_password} <<EOF
CREATE DATABASE IF NOT EXISTS ${IREDAPD_DB_NAME} DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;
USE ${IREDAPD_DB_NAME};
SOURCE /tmp/iredapd.mysql;
GRANT ALL ON ${IREDAPD_DB_NAME}.* TO "${IREDAPD_DB_USER}"@"localhost" IDENTIFIED BY "${IREDAPD_DB_PASSWD}";
SOURCE /tmp/greylisting_whitelists.sql;
FLUSH PRIVILEGES;
EOF

        rm -f /tmp/{iredapd.mysql,greylisting_whitelists.sql}

    elif egrep '^backend.*pgsql' ${IREDAPD_CONF_PY} &>/dev/null; then
        export IREDAPD_DB_PORT='5432'

        # Create database directly.
        cp -f ${PWD}/../SQL/{iredapd.pgsql,greylisting_whitelists.sql} /tmp/
        chmod 0555 /tmp/{iredapd.pgsql,greylisting_whitelists.sql}

        su - ${PGSQL_SYS_USER} -c "psql -d template1" <<EOF
-- Create user, database, change owner
CREATE USER ${IREDAPD_DB_USER} WITH ENCRYPTED PASSWORD '${IREDAPD_DB_PASSWD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE ${IREDAPD_DB_NAME} WITH TEMPLATE template0 ENCODING 'UTF8';
ALTER DATABASE ${IREDAPD_DB_NAME} OWNER TO ${IREDAPD_DB_USER};

\c ${IREDAPD_DB_NAME};

-- Import SQL template
\i /tmp/iredapd.pgsql;

-- Enable greylisting by default
INSERT INTO greylisting (account, priority, sender, sender_priority, active) VALUES ('@.', 0, '@.', 0, 1);

-- Import greylisting whitelists.
\i /tmp/greylisting_whitelists.sql;

-- Grant permissions
GRANT ALL on greylisting, greylisting_tracking, greylisting_whitelists to ${IREDAPD_DB_USER};
GRANT ALL on greylisting_id_seq, greylisting_tracking_id_seq, greylisting_whitelists_id_seq to ${IREDAPD_DB_USER};

GRANT ALL on throttle, throttle_tracking to ${IREDAPD_DB_USER};
GRANT ALL on throttle_id_seq, throttle_tracking_id_seq to ${IREDAPD_DB_USER};
EOF

        su - ${PGSQL_SYS_USER} -c "echo 'localhost:*:*:${IREDAPD_DB_USER}:${IREDAPD_DB_PASSWD}' >> ~/.pgpass"

        rm -f /tmp/{iredapd.pgsql,greylisting_whitelists.sql}
    fi
fi

#
# Add missing/new SQL columns
#
export iredapd_db_server="$(get_value_of_iredapd_setting 'iredapd_db_server')"
export iredapd_db_port="$(get_value_of_iredapd_setting 'iredapd_db_port')"
export iredapd_db_name="$(get_value_of_iredapd_setting 'iredapd_db_name')"
export iredapd_db_user="$(get_value_of_iredapd_setting 'iredapd_db_user')"
export iredapd_db_password="$(get_value_of_iredapd_setting 'iredapd_db_password')"

# Add sql table `greylisting_whitelist_domains`
if egrep '^backend.*(mysql|ldap)' ${IREDAPD_CONF_PY} &>/dev/null; then
    mysql -h${iredapd_db_server} \
          -p${iredapd_db_port} \
          -u${iredapd_db_user} \
          -p${iredapd_db_password} \
          ${iredapd_db_name} <<EOF
CREATE TABLE IF NOT EXISTS greylisting_whitelist_domains (
    id        BIGINT(20)      UNSIGNED AUTO_INCREMENT,
    domain    VARCHAR(255)    NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    UNIQUE INDEX (domain)
) ENGINE=InnoDB;
EOF
elif egrep '^backend.*pgsql' ${IREDAPD_CONF_PY} &>/dev/null; then
    export PGPASSWORD="${iredapd_db_password}"

    psql -h ${iredapd_db_server} \
         -p ${iredapd_db_port} \
         -U ${iredapd_db_user} \
         -d ${iredapd_db_name} \
         -c "SELECT id FROM greylisting_whitelist_domains LIMIT 1" &>/dev/null

    if [ X"$?" != X'0' ]; then
        psql -h ${iredapd_db_server} \
             -p ${iredapd_db_port} \
             -U ${iredapd_db_user} \
             -d ${iredapd_db_name} \
             -c "
CREATE TABLE IF NOT EXISTS greylisting_whitelist_domains (
    id      SERIAL PRIMARY KEY,
    domain  VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelist_domains_domain ON greylisting_whitelist_domains (domain);
"
    fi
fi

#
# Check dependent packages. Prompt to install missed ones manually.
#
echo "* Checking dependent Python modules:"
echo "  + [required] python-sqlalchemy"
if [ X"$(has_python_module sqlalchemy)" == X'NO' ]; then
    [ X"${DISTRO}" == X'RHEL' ]     && install_pkg python-sqlalchemy
    [ X"${DISTRO}" == X'DEBIAN' ]   && install_pkg python-sqlalchemy
    [ X"${DISTRO}" == X'UBUNTU' ]   && install_pkg python-sqlalchemy
    [ X"${DISTRO}" == X'FREEBSD' ]  && install_pkg databases/py-sqlalchemy
    [ X"${DISTRO}" == X'OPENBSD' ]  && install_pkg py-sqlalchemy
fi

echo "  + [required] dnspython"
if [ X"$(has_python_module dns)" == X'NO' ]; then
    [ X"${DISTRO}" == X'RHEL' ]     && install_pkg python-dns
    [ X"${DISTRO}" == X'DEBIAN' ]   && install_pkg python-dnspython
    [ X"${DISTRO}" == X'UBUNTU' ]   && install_pkg python-dnspython
    [ X"${DISTRO}" == X'FREEBSD' ]  && install_pkg dns/py-dnspython
    [ X"${DISTRO}" == X'OPENBSD' ]  && install_pkg py-dnspython
fi


# Copy current directory to Apache server root
dir_new_version="$(dirname ${PWD})"
name_new_version="$(basename ${dir_new_version})"
NEW_IREDAPD_ROOT_DIR="/opt/${name_new_version}"
NEW_IREDAPD_CONF="${NEW_IREDAPD_ROOT_DIR}/settings.py"
if [ ! -d ${NEW_IREDAPD_ROOT_DIR} ]; then
    echo "* Create directory ${NEW_IREDAPD_ROOT_DIR}."
    mkdir ${NEW_IREDAPD_ROOT_DIR} &>/dev/null
fi

echo "* Copying new version to ${NEW_IREDAPD_ROOT_DIR}"
cp -rf ${dir_new_version}/* ${NEW_IREDAPD_ROOT_DIR}

# able to import default settings from libs/default_settings.py
cp -p ${IREDAPD_CONF_PY} ${NEW_IREDAPD_CONF}

if ! grep '^from libs.default_settings import' ${IREDAPD_CONF_PY} &>/dev/null; then
    cat > ${NEW_IREDAPD_CONF}_tmp <<EOF
############################################################
# DO NOT TOUCH BELOW LINE.
#
# Import default settings.
# You can always override default settings by placing custom settings in this
# file.
from libs.default_settings import *
############################################################
EOF

    cat ${NEW_IREDAPD_CONF} >> ${NEW_IREDAPD_CONF}_tmp
    mv ${NEW_IREDAPD_CONF}_tmp ${NEW_IREDAPD_CONF}
fi

chown -R ${SYS_ROOT_USER}:${SYS_ROOT_GROUP} ${NEW_IREDAPD_ROOT_DIR}
chmod -R 0500 ${NEW_IREDAPD_ROOT_DIR}
chmod 0400 ${NEW_IREDAPD_CONF}

echo "* Removing old symbol link ${IREDAPD_ROOT_DIR}"
rm -f ${IREDAPD_ROOT_DIR}

echo "* Creating symbol link ${IREDAPD_ROOT_DIR} to ${NEW_IREDAPD_ROOT_DIR}"
cd /opt && ln -s ${name_new_version} iredapd

#-----------------------------
# Always copy init rc script.
#
echo "* Copy new SysV init script."
if [ X"${DISTRO}" == X'RHEL' ]; then
    cp ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.rhel ${DIR_RC_SCRIPTS}/iredapd
elif [ X"${DISTRO}" == X'DEBIAN' -o X"${DISTRO}" == X'UBUNTU' ]; then
    cp ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.debian ${DIR_RC_SCRIPTS}/iredapd
elif [ X"${DISTRO}" == X"FREEBSD" ]; then
    cp ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.freebsd ${DIR_RC_SCRIPTS}/iredapd
elif [ X"${DISTRO}" == X'OPENBSD' ]; then
    cp ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.openbsd ${DIR_RC_SCRIPTS}/iredapd
fi

systemctl daemon-reload &>/dev/null

chmod 0755 ${DIR_RC_SCRIPTS}/iredapd

#-----------------------------
# Add missing parameters or rename old parameter names."
#
echo "* Add missing parameters or rename old parameter names."

# Get Amavisd related settings from iRedAdmin config file.
if ! grep '^amavisd_db_' ${NEW_IREDAPD_CONF} &>/dev/null; then
    if [ -f ${IREDADMIN_CONF_PY} ]; then
        grep '^amavisd_db_' ${IREDADMIN_CONF_PY} >> ${IREDAPD_CONF_PY}
        perl -pi -e 's#amavisd_db_host#amavisd_db_server#g' ${IREDAPD_CONF_PY}
    else
        # Add sample setting.
        add_missing_parameter 'amavisd_db_server' '127.0.0.1'
        add_missing_parameter 'amavisd_db_port' '3306'
        add_missing_parameter 'amavisd_db_name' 'amavisd'
        add_missing_parameter 'amavisd_db_user' 'amavisd'
        add_missing_parameter 'amavisd_db_password' 'password'
    fi
fi

# iRedAPD related settings.
if ! grep '^iredapd_db_' ${NEW_IREDAPD_CONF} &>/dev/null; then
    # Add required settings.
    add_missing_parameter 'iredapd_db_server' "${IREDAPD_DB_SERVER}"
    add_missing_parameter 'iredapd_db_port' "${IREDAPD_DB_PORT}"
    add_missing_parameter 'iredapd_db_name' "${IREDAPD_DB_NAME}"
    add_missing_parameter 'iredapd_db_user' "${IREDAPD_DB_USER}"
    add_missing_parameter 'iredapd_db_password' "${IREDAPD_DB_PASSWD}"
fi

# replace old parameter names: sql_[XX] -> vmail_db_[XX]
if grep '^sql_server' ${IREDAPD_CONF_PY} &>/dev/null; then
    perl -pi -e 's#^(sql_db)#vmail_db_name#g' ${IREDAPD_CONF_PY}
    perl -pi -e 's#^(sql_)#vmail_db_#g' ${IREDAPD_CONF_PY}
fi

#------------------------------
# Remove old plugins
#
echo "* Remove deprecated plugins."
rm -f ${IREDAPD_ROOT_DIR}/plugins/ldap_amavisd_block_blacklisted_senders.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/plugins/ldap_recipient_restrictions.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/plugins/sql_user_restrictions.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/plugins/amavisd_message_size_limit.py &>/dev/null

#------------------------------
# Log rotate
#
# Create directory to store log files.
if [ ! -d ${IREDAPD_LOG_DIR} ]; then
    echo "* Create directory to store log files: ${IREDAPD_LOG_DIR}."
    mkdir -p ${IREDAPD_LOG_DIR} 2>/dev/null
fi

# Move old log files to log directory.
[ -f /var/log/iredapd.log ] && mv /var/log/iredapd.log* ${IREDAPD_LOG_DIR}

# Always set correct owner and permission, so that we can rotate the log files.
chown -R ${IREDAPD_DAEMON_USER}:${IREDAPD_DAEMON_GROUP} ${IREDAPD_LOG_DIR}
chmod -R 0700 ${IREDAPD_LOG_DIR}

# Always reset log file.
perl -pi -e 's#^(log_file).*#${1} = "$ENV{IREDAPD_LOG_FILE}"#' ${IREDAPD_CONF_PY}

# Remove old logrotate config file.
# Linux
[ -f /etc/logrotate.d/iredapd ] && rm -f /etc/logrotate.d/iredapd
# FreeBSD & OpenBSD
[ -f /etc/newsyslog.conf ] && perl -pi -e 's|^(/var/log/iredapd.log.)|#${1}|' /etc/newsyslog.conf

#------------------------------
# Cron job.
#
# /opt/iRedAPD-* will be owned by root user, so we have to add cron job for
# root user instead of iredapd daemon user.
CRON_FILE="${CRON_SPOOL_DIR}/${SYS_ROOT_USER}"

[[ -d ${CRON_SPOOL_DIR} ]] || mkdir -p ${CRON_SPOOL_DIR} &>/dev/null
if [[ ! -f ${CRON_FILE} ]]; then
    touch ${CRON_FILE} &>/dev/null
    chmod 0600 ${CRON_FILE} &>/dev/null
fi

# cron job for cleaning up database.
if ! grep '/opt/iredapd/tools/cleanup_db.py' ${CRON_FILE} &>/dev/null; then
    cat >> ${CRON_FILE} <<EOF
# iRedAPD: Clean up expired tracking records hourly.
1   *   *   *   *   ${PYTHON_BIN} ${IREDAPD_ROOT_DIR}/tools/cleanup_db.py &>/dev/null
EOF
fi

# cron job for updating IP addresses/networks of greylisting whitelist domains.
if ! grep '/opt/iredapd/tools/spf_to_greylisting_whitelists.py' ${CRON_FILE} &>/dev/null; then
    cat >> ${CRON_FILE} <<EOF
# iRedAPD: Update IP addresses/networks of greylisting whitelist domains.
1   3   *   *   *   ${PYTHON_BIN} ${IREDAPD_ROOT_DIR}/tools/spf_to_greylisting_whitelists.py &>/dev/null
EOF
fi


#------------------------------
# Post-upgrade, clean up.
#
echo "* Restarting iRedAPD service."
if [ X"${KERNEL_NAME}" == X'LINUX' ]; then
    service ${RC_SCRIPT_NAME} restart
elif [ X"${KERNEL_NAME}" == X'FREEBSD' ]; then
    /usr/local/etc/rc.d/${RC_SCRIPT_NAME} restart
elif [ X"${KERNEL_NAME}" == X'OPENBSD' ]; then
    /etc/rc.d/${RC_SCRIPT_NAME} restart
fi

if [ X"$?" != X'0' ]; then
    echo "Failed, please restart iRedAPD service manually."
fi

echo "* Upgrade completed."

cat <<EOF
<<< NOTE >>> If iRedAPD doesn't work as expected, please post your issue in
<<< NOTE >>> our online support forum: http://www.iredmail.org/forum/
<<< NOTE >>> iRedAPD log file is ${IREDAPD_LOG_FILE}.
EOF
