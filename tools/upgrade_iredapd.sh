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

export CRON_FILE_ROOT="${CRON_SPOOL_DIR}/${SYS_ROOT_USER}"

# iRedAPD directory and config file.
export IREDAPD_ROOT_DIR="/opt/iredapd"
export IREDAPD_CONF_PY="${IREDAPD_ROOT_DIR}/settings.py"
export IREDAPD_CONF_INI="${IREDAPD_ROOT_DIR}/settings.ini"
# Used in iRedMail cluster and iRedMail-Pro edition.
export IREDAPD_CUSTOM_CONF="${IREDAPD_ROOT_DIR}/custom_settings.py"

# Remove all single quote and double quotes in string.
strip_quotes()
{
    # Read input from stdin
    str="$(cat <&0)"

    value="$(echo ${str} | tr -d '"' | tr -d "'")"

    echo "${value}"
}

get_iredapd_setting()
{
    # Usage: get_iredapd_setting <path_to_config_file> <var_name>
    conf_py="${1}"
    var="${2}"

    value="$(grep "^${var}" ${conf_py} | awk '{print $NF}' | strip_quotes)"

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

# Check /root/.my.cnf. This will make sql related changes much simpler.
if [ -f ${IREDAPD_CONF_PY} ]; then
    if egrep '^backend.*(mysql|ldap)' ${IREDAPD_CONF_PY} &>/dev/null; then
        if [ ! -f /root/.my.cnf ]; then
            echo "<<< ERROR >>> File /root/.my.cnf not found."
            echo "<<< ERROR >>> Please add mysql root user and password in it like below, then run this script again."
            cat <<EOF

[client]
host=127.0.0.1
port=3306
user=root
password="plain_password"

EOF

            exit 255
        fi

        # Check MySQL connection
        mysql -e "SHOW DATABASES" &>/dev/null
        if [ X"$?" != X'0' ]; then
            echo "<<< ERROR >>> MySQL root user name or password is incorrect in /root/.my.cnf, please double check."
            exit 255
        fi
    fi
fi

echo "* Detected Linux/BSD distribution: ${DISTRO}"

if [ -L ${IREDAPD_ROOT_DIR} ]; then
    export IREDAPD_ROOT_REAL_DIR="$(readlink ${IREDAPD_ROOT_DIR})"
    echo "* Found iRedAPD directory: ${IREDAPD_ROOT_DIR}, symbol link of ${IREDAPD_ROOT_REAL_DIR}"
else
    echo "<<< ERROR >>> Directory is not a symbol link created by iRedMail. Exit."
    exit 255
fi

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

remove_parameter()
{
    # Usage: remove_parameter <var_name>
    export var="${1}"

    if grep "^${var}" ${IREDAPD_CONF_PY} &>/dev/null; then
        perl -pi -e 's#^($ENV{var}.*)##g' ${IREDAPD_CONF_PY}
    fi

    unset var
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

mkdir /tmp/iredapd/ 2>/dev/null
cp -f ${PWD}/../SQL/*sql /tmp/iredapd
chmod -R 0555 /tmp/iredapd

#
# Require SQL root password to create `iredapd` database.
#
export IREDAPD_DB_NAME='iredapd'
if ! grep '^iredapd_db_' ${IREDAPD_CONF_PY} &>/dev/null; then
    export IREDAPD_DB_SERVER='127.0.0.1'
    export IREDAPD_DB_USER='iredapd'
    export IREDAPD_DB_PASSWD="$(echo $RANDOM | ${MD5_BIN} | awk '{print $1}')"

    mkdir /tmp/iredapd/ 2>/dev/null
    cp -f ${PWD}/../SQL/*sql /tmp/iredapd
    chmod -R 0555 /tmp/iredapd

    # Check backend.
    if egrep '^backend.*(mysql|ldap)' ${IREDAPD_CONF_PY} &>/dev/null; then
        export IREDAPD_DB_PORT='3306'

        # Create database and tables.
        mysql <<EOF
CREATE DATABASE IF NOT EXISTS ${IREDAPD_DB_NAME} DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci;
USE ${IREDAPD_DB_NAME};

SOURCE /tmp/iredapd/iredapd.mysql;
SOURCE /tmp/iredapd/enable_global_greylisting.sql;
SOURCE /tmp/iredapd/greylisting_whitelist_domains.sql;
SOURCE /tmp/iredapd/wblist_rdns.sql;

GRANT ALL ON ${IREDAPD_DB_NAME}.* TO "${IREDAPD_DB_USER}"@"localhost" IDENTIFIED BY "${IREDAPD_DB_PASSWD}";
FLUSH PRIVILEGES;
EOF
    elif egrep '^backend.*pgsql' ${IREDAPD_CONF_PY} &>/dev/null; then
        export IREDAPD_DB_PORT='5432'

        su - ${PGSQL_SYS_USER} -c "psql -d template1" <<EOF
-- Create user, database, change owner
CREATE USER ${IREDAPD_DB_USER} WITH ENCRYPTED PASSWORD '${IREDAPD_DB_PASSWD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE ${IREDAPD_DB_NAME} WITH TEMPLATE template0 ENCODING 'UTF8';
ALTER DATABASE ${IREDAPD_DB_NAME} OWNER TO ${IREDAPD_DB_USER};

\c ${IREDAPD_DB_NAME};

-- Import SQL templates
\i /tmp/iredapd/iredapd.pgsql;
\i /tmp/iredapd/enable_global_greylisting.sql;
\i /tmp/iredapd/greylisting_whitelist_domains.sql;
\i /tmp/iredapd/wblist_rdns.sql;

-- Grant permissions
GRANT ALL ON greylisting, greylisting_tracking, greylisting_whitelists, greylisting_whitelist_domains TO ${IREDAPD_DB_USER};
GRANT ALL ON greylisting_id_seq, greylisting_tracking_id_seq, greylisting_whitelists_id_seq, greylisting_whitelist_domains_id_seq TO ${IREDAPD_DB_USER};

GRANT ALL ON throttle, throttle_tracking TO ${IREDAPD_DB_USER};
GRANT ALL ON throttle_id_seq, throttle_tracking_id_seq TO ${IREDAPD_DB_USER};
GRANT ALL ON wblist_rdns,wblist_rdns_id_seq TO ${IREDAPD_DB_USER};
EOF

        su - ${PGSQL_SYS_USER} -c "echo 'localhost:*:*:${IREDAPD_DB_USER}:${IREDAPD_DB_PASSWD}' >> ~/.pgpass"
    fi

    rm -rf /tmp/iredapd
fi

#
# Add missing/new SQL tables
#
export iredapd_db_server="$(get_iredapd_setting ${IREDAPD_CONF_PY} 'iredapd_db_server')"
export iredapd_db_port="$(get_iredapd_setting ${IREDAPD_CONF_PY} 'iredapd_db_port')"
export iredapd_db_name="$(get_iredapd_setting ${IREDAPD_CONF_PY} 'iredapd_db_name')"
export iredapd_db_user="$(get_iredapd_setting ${IREDAPD_CONF_PY} 'iredapd_db_user')"
export iredapd_db_password="$(get_iredapd_setting ${IREDAPD_CONF_PY} 'iredapd_db_password')"

if [ X"${DISTRO}" == X'OPENBSD' -a X"${iredapd_db_server}" == X'127.0.0.1' ]; then
    export iredapd_db_server='localhost'
fi

#
# Update sql tables
#
mysql_conn="mysql ${iredapd_db_name}"
psql_conn="psql -h ${iredapd_db_server} \
                -p ${iredapd_db_port} \
                -U ${iredapd_db_user} \
                -d ${iredapd_db_name}"

if egrep '^backend.*(mysql|ldap)' ${IREDAPD_CONF_PY} &>/dev/null; then
    cp -f ${PWD}/../SQL/iredapd.mysql /tmp/

    #
    # `greylisting_whitelist_domains`
    #
    (${mysql_conn} <<EOF
show tables;
EOF
) | grep 'greylisting_whitelist_domains' &>/dev/null

    if [ X"$?" != X'0' ]; then
        cp -f ${PWD}/../SQL/greylisting_whitelist_domains.sql /tmp/
        chmod 0555 /tmp/greylisting_whitelist_domains.sql

        ${mysql_conn} <<EOF
SOURCE /tmp/iredapd.mysql;
SOURCE /tmp/greylisting_whitelist_domains.sql;
EOF
    fi

    #
    # alter some columns to BIGINT(20): throttle.{msg_size,max_quota,max_msgs}
    #
    ${mysql_conn} <<EOF
ALTER TABLE throttle MODIFY COLUMN msg_size  BIGINT(20) NOT NULL DEFAULT -1;
ALTER TABLE throttle MODIFY COLUMN max_msgs  BIGINT(20) NOT NULL DEFAULT -1;
ALTER TABLE throttle MODIFY COLUMN max_quota BIGINT(20) NOT NULL DEFAULT -1;
EOF

    #
    # INDEX on `greylisting_tracking`: (client_address, passed)
    #
    (${mysql_conn} <<EOF
SHOW INDEX FROM greylisting_tracking \G
EOF
) | grep 'Key_name: client_address_passed$' &>/dev/null

    if [ X"$?" != X'0' ]; then
        ${mysql_conn} -e "CREATE INDEX client_address_passed ON greylisting_tracking (client_address, passed);"
    fi

    #
    # `greylisting_whitelist_domain_spf`
    #
    (${mysql_conn} <<EOF
show tables;
EOF
) | grep 'greylisting_whitelist_domain_spf' &>/dev/null

    if [ X"$?" != X'0' ]; then
        ${mysql_conn} <<EOF
SOURCE /tmp/iredapd.mysql;
EOF
    fi

    #
    # `wblist_rdns`
    #
    (${mysql_conn} <<EOF
show tables;
EOF
) | grep 'wblist_rdns' &>/dev/null

    if [ X"$?" != X'0' ]; then
        cp -f ${PWD}/../SQL/wblist_rdns.sql /tmp/
        chmod 0555 /tmp/wblist_rdns.sql

        ${mysql_conn} <<EOF
SOURCE /tmp/iredapd.mysql;
SOURCE /tmp/wblist_rdns.sql;
EOF
    fi

elif egrep '^backend.*pgsql' ${IREDAPD_CONF_PY} &>/dev/null; then
    export PGPASSWORD="${iredapd_db_password}"

    #
    # `greylisting_whitelist_domains`
    #
    ${psql_conn} -c "SELECT id FROM greylisting_whitelist_domains LIMIT 1" &>/dev/null

    if [ X"$?" != X'0' ]; then
        cp -f ${PWD}/../SQL/greylisting_whitelist_domains.sql /tmp/
        chmod 0555 /tmp/greylisting_whitelist_domains.sql

        ${psql_conn} -c "
CREATE TABLE greylisting_whitelist_domains (
    id      SERIAL PRIMARY KEY,
    domain  VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelist_domains_domain ON greylisting_whitelist_domains (domain);
\i /tmp/greylisting_whitelist_domains.sql;
"

        rm -f /tmp/greylisting_whitelist_domains.sql &>/dev/null
    fi

    #
    # `greylisting_whitelist_domain_spf`
    #
    ${psql_conn} -c "SELECT id FROM greylisting_whitelist_domain_spf LIMIT 1" &>/dev/null

    if [ X"$?" != X'0' ]; then
        ${psql_conn} -c "
CREATE TABLE greylisting_whitelist_domain_spf (
    id      SERIAL PRIMARY KEY,
    account VARCHAR(255)    NOT NULL DEFAULT '',
    sender  VARCHAR(255)    NOT NULL DEFAULT '',
    comment VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelist_domain_spf_account_sender ON greylisting_whitelist_domain_spf (account, sender);
CREATE INDEX idx_greylisting_whitelist_domain_spf_comment ON greylisting_whitelist_domain_spf (comment);
"
    fi

    #
    # `wblist_rdns`
    #
    ${psql_conn} -c "SELECT id FROM wblist_rdns LIMIT 1" &>/dev/null

    if [ X"$?" != X'0' ]; then
        cp -f ${PWD}/../SQL/wblist_rdns.sql /tmp/
        chmod 0555 /tmp/wblist_rdns.sql

        ${psql_conn} <<EOF
CREATE TABLE wblist_rdns (
    id      SERIAL PRIMARY KEY,
    -- reverse DNS name of sender IP address
    rdns    VARCHAR(255) NOT NULL DEFAULT '',
    -- W=whitelist, B=blacklist
    wb      VARCHAR(10) NOT NULL DEFAULT 'B'
);
CREATE UNIQUE INDEX idx_wblist_rdns_rdns ON wblist_rdns (rdns);
CREATE INDEX idx_wblist_rdns_wb ON wblist_rdns (wb);
\i /tmp/wblist_rdns.sql;
EOF

        rm -f /tmp/wblist_rdns.sql &>/dev/null
    fi

    #
    # INDEX on `greylisting_tracking`: (client_address, passed)
    #
    ${psql_conn} -c "SELECT indexname FROM pg_indexes WHERE indexname='idx_greylisting_tracking_client_address_passed'" | grep 'idx_greylisting_tracking_client_address_passed' &>/dev/null

    if [ X"$?" != X'0' ]; then
        ${psql_conn} -c "CREATE INDEX idx_greylisting_tracking_client_address_passed ON greylisting_tracking (client_address, passed);"
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


#
# Upgrade to new version
#
# Copy current directory to web DocumentRoot
dir_new_version="$(dirname ${PWD})"
name_new_version="$(basename ${dir_new_version})"
NEW_IREDAPD_ROOT_DIR="/opt/${name_new_version}"
NEW_IREDAPD_CONF="${NEW_IREDAPD_ROOT_DIR}/settings.py"
NEW_IREDAPD_CUSTOM_CONF="${NEW_IREDAPD_ROOT_DIR}/custom_settings.py"

if [ ! -d ${NEW_IREDAPD_ROOT_DIR} ]; then
    echo "* Create directory ${NEW_IREDAPD_ROOT_DIR}."
    mkdir ${NEW_IREDAPD_ROOT_DIR} &>/dev/null
fi

echo "* Copying new version to ${NEW_IREDAPD_ROOT_DIR}"
cp -rf ${dir_new_version}/* ${NEW_IREDAPD_ROOT_DIR}

echo "* Copy old config file: settings.py (${IREDAPD_CONF_PY} -> ${NEW_IREDAPD_CONF})"
cp -p ${IREDAPD_CONF_PY} ${NEW_IREDAPD_CONF}

[ -f ${IREDAPD_CUSTOM_CONF} ] && \
    cp -p ${IREDAPD_CUSTOM_CONF} ${NEW_IREDAPD_CUSTOM_CONF}

echo "* Copy custom plugins: ${IREDAPD_ROOT_REAL_DIR}/plugins/custom_*.py."
cp -rf ${IREDAPD_ROOT_REAL_DIR}/plugins/custom_* ${NEW_IREDAPD_ROOT_DIR}/plugins/ 2>/dev/null

# Import settings from libs/default_settings.py
if ! grep '^from libs.default_settings import' ${IREDAPD_CONF_PY} &>/dev/null; then
    echo "* Update settings.py to import settings from libs/default_settings.py."
    cat > ${NEW_IREDAPD_CONF}_tmp <<EOF
################################################################
# DO NOT MODIFY THIS LINE, IT'S USED TO IMPORT DEFAULT SETTINGS.
from libs.default_settings import *
################################################################
EOF

    cat ${NEW_IREDAPD_CONF} >> ${NEW_IREDAPD_CONF}_tmp
    mv ${NEW_IREDAPD_CONF}_tmp ${NEW_IREDAPD_CONF}
fi

echo "* Set correct owner and permission for ${NEW_IREDAPD_ROOT_DIR}: ${SYS_ROOT_USER}:${SYS_ROOT_GROUP}, 0500."
chown -R ${SYS_ROOT_USER}:${SYS_ROOT_GROUP} ${NEW_IREDAPD_ROOT_DIR}
chmod -R 0500 ${NEW_IREDAPD_ROOT_DIR}

echo "* Set permission for iRedAPD config file: ${NEW_IREDAPD_CONF} -> 0400."
chmod 0400 ${NEW_IREDAPD_CONF}

echo "* Re-create symbol link: ${IREDAPD_ROOT_DIR} -> ${NEW_IREDAPD_ROOT_DIR}"
rm -f ${IREDAPD_ROOT_DIR}
cd /opt && ln -s ${name_new_version} iredapd

export USE_SYSTEMD='NO'
if which systemctl &>/dev/null; then
    export USE_SYSTEMD='YES'
    export SYSTEMD_SERVICE_DIR='/lib/systemd/system'
    export SYSTEMD_SERVICE_USER_DIR='/etc/systemd/system/multi-user.target.wants/'
fi

# Always copy init rc script.
if [ -f "${DIR_RC_SCRIPTS}/iredapd" ]; then
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

    chmod 0755 ${DIR_RC_SCRIPTS}/iredapd
else
    if [ X"${USE_SYSTEMD}" == X'YES' ]; then
        echo "* Create symbol link: ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.service -> ${SYSTEMD_SERVICE_DIR}/iredapd.service."
        rm -f ${SYSTEMD_SERVICE_DIR}/iredapd.service ${SYSTEMD_SERVICE_USER_DIR}/iredapd.service &>/dev/null
        cp -f ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.service ${SYSTEMD_SERVICE_DIR}/iredapd.service
        chmod -R 0640 ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.service
        systemctl daemon-reload &>/dev/null
        systemctl enable iredapd.service >/dev/null
    fi
fi

# For systems which use systemd
systemctl daemon-reload &>/dev/null

#-----------------------------------------------
# Post-upgrade
#-----------------------------

#
# Add missing parameters or rename old parameter names."
#
# Get Amavisd related settings from iRedAdmin config file.
if ! grep '^amavisd_db_' ${NEW_IREDAPD_CONF} &>/dev/null; then
    echo "* Add missing parameters used for plugin 'amavisd_wblist'."

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
# Remove unused parameters
#
remove_parameter 'log_action_in_db'
remove_parameter 'iredadmin_db_server'
remove_parameter 'iredadmin_db_port'
remove_parameter 'iredadmin_db_name'
remove_parameter 'iredadmin_db_user'
remove_parameter 'iredadmin_db_password'

#------------------------------
# Remove old plugins
#
echo "* Remove deprecated plugins."
rm -f ${IREDAPD_ROOT_DIR}/plugins/ldap_amavisd_block_blacklisted_senders.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/ldap_recipient_restrictions.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/sql_user_restrictions.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/amavisd_message_size_limit.py &>/dev/null

#------------------------------
# Rename old plugins
#
echo "* Rename old plugins."
perl -pi -e 's#sql_force_change_password_in_days#sql_force_change_password#g' ${IREDAPD_CONF_PY}
perl -pi -e 's#ldap_force_change_password_in_days#ldap_force_change_password#g' ${IREDAPD_CONF_PY}

#------------------------------
# Log rotate
#
# Create directory which is used to store log files.
if [ ! -d ${IREDAPD_LOG_DIR} ]; then
    echo "* Create directory to store log files: ${IREDAPD_LOG_DIR}."
    mkdir -p ${IREDAPD_LOG_DIR} 2>/dev/null
fi

# Move old log files to log directory.
mv /var/log/iredapd.log* ${IREDAPD_LOG_DIR} &>/dev/null

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
# /opt/iRedAPD-* is owned by root user, so we have to add cron job for
# root user instead of iredapd daemon user.
[[ -d ${CRON_SPOOL_DIR} ]] || mkdir -p ${CRON_SPOOL_DIR} &>/dev/null
if [[ ! -f ${CRON_FILE_ROOT} ]]; then
    touch ${CRON_FILE_ROOT} &>/dev/null
    chmod 0600 ${CRON_FILE_ROOT} &>/dev/null
fi

# cron job for cleaning up database.
if ! grep '/opt/iredapd/tools/cleanup_db.py' ${CRON_FILE_ROOT} &>/dev/null; then
    cat >> ${CRON_FILE_ROOT} <<EOF
# iRedAPD: Clean up expired tracking records hourly.
1   *   *   *   *   ${PYTHON_BIN} ${IREDAPD_ROOT_DIR}/tools/cleanup_db.py &>/dev/null
EOF
fi

# cron job for updating IP addresses/networks of greylisting whitelist domains.
if ! grep 'spf_to_greylist_whitelists.py' ${CRON_FILE_ROOT} &>/dev/null; then
    cat >> ${CRON_FILE_ROOT} <<EOF
# iRedAPD: Convert specified SPF DNS record of specified domain names to IP
#          addresses/networks every 10 minutes.
*/30   *   *   *   *   ${PYTHON_BIN} ${IREDAPD_ROOT_DIR}/tools/spf_to_greylist_whitelists.py &>/dev/null
EOF
fi


#------------------------------
# Clean up.
#
if [ -e /tmp/iredapd ]; then
    echo "* Remove /tmp/iredapd"
    rm -rf /tmp/iredapd &>/dev/null
fi

echo "* Remove all *.pyc files."
cd ${IREDAPD_ROOT_DIR} && find . -name '*.pyc' | xargs rm -f {} &>/dev/null

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

< NOTE > If iRedAPD doesn't work as expected, please post your issue in our
< NOTE > online support forum: http://www.iredmail.org/forum/
< NOTE >
< NOTE > * Turn on debug mode: http://www.iredmail.org/docs/debug.iredapd.html
< NOTE > * iRedAPD log file is ${IREDAPD_LOG_FILE}.

EOF
