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

tmprootdir="$(dirname $0)"
echo ${tmprootdir} | grep '^/' >/dev/null 2>&1
if [ X"$?" == X"0" ]; then
    export ROOTDIR="${tmprootdir}"
else
    export ROOTDIR="$(pwd)"
fi

export SYS_USER_ROOT='root'
export SYS_GROUP_ROOT='root'
export SYS_USER_SYSLOG='root'
export SYS_GROUP_SYSLOG='root'

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
export CMD_PYTHON3='/usr/bin/python3'
export CMD_PIP3='/usr/bin/pip3'

if [ X"${KERNEL_NAME}" == X'LINUX' ]; then
    export DIR_RC_SCRIPTS='/etc/init.d'
    export SYSLOG_CONF_DIR='/etc/rsyslog.d'
    export LOGROTATE_DIR='/etc/logrotate.d'

    if [ -f /etc/redhat-release ]; then
        # RHEL/CentOS
        export DISTRO='RHEL'
        export IREDADMIN_CONF_PY='/var/www/iredadmin/settings.py'
        export CRON_SPOOL_DIR='/var/spool/cron'

        # Get an check relese version.
        if grep '\ 7\.' /etc/redhat-release &>/dev/null; then
            export DISTRO_VERSION='7'
        elif grep '\ 8\.' /etc/redhat-release &>/dev/null; then
            export DISTRO_VERSION='8'
            export CMD_PIP3='/usr/bin/pip3.6'
        else
            export UNSUPPORTED_RELEASE="YES"
        fi
    elif [ -f /etc/lsb-release ]; then
        # Ubuntu
        export DISTRO='UBUNTU'

        # Ubuntu version number and code name:
        #   - 18.04: bionic
        #   - 20.04: focal
        export DISTRO_VERSION="$(awk -F'=' '/^DISTRIB_RELEASE/ {print $2}' /etc/lsb-release)"
        export DISTRO_CODENAME="$(awk -F'=' '/^DISTRIB_CODENAME/ {print $2}' /etc/lsb-release)"

        if echo "${DISTRO_VERSION}" | grep '^1[4567]' &>/dev/null; then
            echo "[ERROR] Your Ubuntu release ${DISTRO_VERSION} is too old and not supported."
            exit 255
        fi

        # Syslog
        export SYS_USER_SYSLOG='syslog'
        export SYS_GROUP_SYSLOG='adm'

        if [ -f '/usr/share/apache2/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/usr/share/apache2/iredadmin/settings.py'
        elif [ -f '/opt/www/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/opt/www/iredadmin/settings.py'
        fi
        export CRON_SPOOL_DIR='/var/spool/cron/crontabs'

    elif [ -f /etc/debian_version ]; then
        # Debian
        export DISTRO='DEBIAN'

        # Set distro code name and unsupported releases.
        if grep -i '^10' /etc/debian_version &>/dev/null; then
            export DISTRO_VERSION='10'
        elif grep '^9' /etc/debian_version &>/dev/null || \
            grep -i '^stretch' /etc/debian_version &>/dev/null; then
            export DISTRO_VERSION='9'
        else
            export UNSUPPORTED_RELEASE="YES"
        fi

        # Syslog
        export SYS_GROUP_SYSLOG='adm'

        if [ -f '/usr/share/apache2/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/usr/share/apache2/iredadmin/settings.py'
        elif [ -f '/opt/www/iredadmin/settings.py' ]; then
            export IREDADMIN_CONF_PY='/opt/www/iredadmin/settings.py'
        fi
        export CRON_SPOOL_DIR='/var/spool/cron/crontabs'
    else
        export UNSUPPORTED_RELEASE="YES"
    fi

elif [ X"${KERNEL_NAME}" == X'FREEBSD' ]; then
    export DISTRO='FREEBSD'
    export SYS_GROUP_ROOT='wheel'
    export SYS_GROUP_SYSLOG='wheel'
    export PGSQL_SYS_USER='pgsql'
    export SYSLOG_CONF_DIR='/usr/local/etc/syslog.d'
    export LOGROTATE_DIR='/usr/local/etc/newsyslog.conf.d'
    export DIR_RC_SCRIPTS='/usr/local/etc/rc.d'
    export IREDADMIN_CONF_PY='/usr/local/www/iredadmin/settings.py'
    export CRON_SPOOL_DIR='/var/cron/tabs'
    export CMD_PYTHON3='/usr/local/bin/python3'
    export CMD_PIP3='/usr/local/bin/pip3'

elif [ X"${KERNEL_NAME}" == X'OPENBSD' ]; then
    export DISTRO='OPENBSD'
    export DISTRO_VERSION="$(uname -r)"
    export SYS_GROUP_ROOT='wheel'
    export SYS_GROUP_SYSLOG='wheel'
    export PGSQL_SYS_USER='_postgresql'
    export DIR_RC_SCRIPTS='/etc/rc.d'
    export IREDADMIN_CONF_PY='/var/www/iredadmin/settings.py'
    export CRON_SPOOL_DIR='/var/cron/tabs'

    if [ X"${DISTRO_VERSION}" == X'6.8' ]; then
        export CMD_PYTHON3='/usr/local/bin/python3.8'
        export CMD_PIP3='/usr/local/bin/pip3.8'
    elif [ X"${DISTRO_VERSION}" == X'6.6' -o X"${DISTRO_VERSION}" == X'6.7' ]; then
        export CMD_PYTHON3='/usr/local/bin/python3.7'
        export CMD_PIP3='/usr/local/bin/pip3.7'
    else
        echo "Unsupported OpenBSD release: ${DISTRO_VERSION}. Abort."
        exit 255
    fi
else
    echo "Cannot detect Linux/BSD distribution. Exit."
    echo "Please contact author iRedMail team <support@iredmail.org> to solve it."
    exit 255
fi

if [ X"${UNSUPPORTED_RELEASE}" == X'YES' ]; then
    echo "Unsupported Linux/BSD distribution or release, abort."
    exit 255
fi

if [ X"${KERNEL_NAME}" == X'OPENBSD' ]; then
    export HOSTNAME="$(hostname)"

    # Command used to genrate a random string.
    # Usage: str="$(${RANDOM_STRING})"
    export RANDOM_STRING='eval </dev/random tr -cd [:alnum:] | fold -w 32 | head -1'
else
    export HOSTNAME="$(hostname -f)"
    export RANDOM_STRING='eval </dev/urandom tr -dc A-Za-z0-9 | (head -c $1 &>/dev/null || head -c 32)'
fi

export CRON_FILE_ROOT="${CRON_SPOOL_DIR}/${SYS_USER_ROOT}"

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

install_pkgs()
{
    if [ X"${DISTRO}" == X'RHEL' ]; then
        echo "Install packages: $@"
        yum -y install $@
    elif [ X"${DISTRO}" == X'DEBIAN' -o X"${DISTRO}" == X'UBUNTU' ]; then
        echo "Install packages: $@"
        apt-get install -y --force-yes $@
    elif [ X"${DISTRO}" == X'FREEBSD' ]; then
        for _port in $@; do
            echo "Install package: ${_port}"
            cd /usr/ports/${_port}
            make USES=python:3.5+ install clean
        done
    elif [ X"${DISTRO}" == X'OPENBSD' ]; then
        echo "Install packages: $@"
        pkg_add -r $@
    else
        echo "<< ERROR >> Please install package(s) manually: $@"
    fi
}

has_python_module()
{
    for mod in $@; do
        ${CMD_PYTHON3} -c "import $mod" &>/dev/null
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

remove_parameter()
{
    # Usage: remove_parameter <var_name>
    export var="${1}"

    if grep "^${var}" ${IREDAPD_CONF_PY} &>/dev/null; then
        perl -pi -e 's#^($ENV{var}.*)##g' ${IREDAPD_CONF_PY}
    fi

    unset var
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

#
# Check dependent packages.
#
DEP_PKGS=""
DEP_PIP3_MODS=""

# Install python3.
if [ ! -x ${CMD_PYTHON3} ]; then
    if [ X"${DISTRO}" == X'RHEL' ]; then
        [[ X"${DISTRO_VERSION}" == X'7' ]] && DEP_PKGS="${DEP_PKGS} python3 python3-pip"
        [[ X"${DISTRO_VERSION}" == X'8' ]] && DEP_PKGS="${DEP_PKGS} python36 python3-pip"
    fi

    [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3 python3-pip"
    [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3 python3-pip"
    [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} lang/python38 devel/py-pip"

    if [ X"${DISTRO}" == X'OPENBSD' ]; then
        if [ X"${DISTRO_VERSION}" == X'6.8' ]; then
            DEP_PKGS="${DEP_PKGS} python%3.8"
        elif [ X"${DISTRO_VERSION}" == X'6.6' -o X"${DISTRO_VERSION}" == X'6.7' ]; then
            DEP_PKGS="${DEP_PKGS} python%3.7"
        fi
    fi
fi

if [ ! -x ${CMD_PIP3} ]; then
    [ X"${DISTRO}" == X'RHEL' ] && DEP_PKGS="${DEP_PKGS} python3-pip"
    [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-pip"
    [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-pip"
    [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} devel/py-pip"
    [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-pip"
fi

echo "* Checking dependent Python modules:"

echo "  + [required] wheel"
if [ X"$(has_python_module wheel)" == X'NO' ]; then
    [ X"${DISTRO}" == X'RHEL' ] && DEP_PKGS="${DEP_PKGS} python3-wheel"
    [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-wheel"
    [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-wheel"
    [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} devel/py-wheel"
    [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-wheel"
fi

echo "  + [required] sqlalchemy"
if [ X"$(has_python_module sqlalchemy)" == X'NO' ]; then
    if [ X"${DISTRO}" == X'RHEL' ]; then
        [[ X"${DISTRO_VERSION}" == X'7' ]] && DEP_PKGS="${DEP_PKGS} python36-sqlalchemy"
        [[ X"${DISTRO_VERSION}" == X'8' ]] && DEP_PKGS="${DEP_PKGS} python3-sqlalchemy"
    fi

    [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-sqlalchemy"
    [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-sqlalchemy"
    [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} databases/py-sqlalchemy"
    [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-sqlalchemy"
fi

echo "  + [required] dnspython"
if [ X"$(has_python_module dns)" == X'NO' ]; then
    if [ X"${DISTRO}" == X'RHEL' ]; then
        [ X"${DISTRO_VERSION}" == X'7' ] && DEP_PKGS="${DEP_PKGS} python36-dns"
        [ X"${DISTRO_VERSION}" == X'8' ] && DEP_PKGS="${DEP_PKGS} python3-dns"
    fi

    [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-dnspython"
    [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-dnspython"
    [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} dns/py-dnspython"
    [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-dnspython"
fi

echo "  + [required] requests"
if [ X"$(has_python_module requests)" == X'NO' ]; then
    if [ X"${DISTRO}" == X'RHEL' ]; then
        [ X"${DISTRO_VERSION}" == X'7' ] && DEP_PKGS="${DEP_PKGS} python36-requests"
        [ X"${DISTRO_VERSION}" == X'8' ] && DEP_PKGS="${DEP_PKGS} python3-requests"
    fi

    [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-requests"
    [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-requests"
    [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} dns/py-requests"
    [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-requests"
fi

echo "  + [required] web.py"
if [ X"$(has_python_module web)" == X'NO' ]; then
    DEP_PIP3_MODS="${DEP_PIP3_MODS} web.py>=0.61"
fi

if grep '^backend' ${IREDAPD_CONF_PY} | grep 'ldap' &>/dev/null; then
    # LDAP backend
    export IREDMAIL_BACKEND='OPENLDAP'

    if [ X"$(has_python_module ldap)" == X'NO' ]; then
        if [ X"${DISTRO}" == X'RHEL' ]; then
            if [ X"${DISTRO_VERSION}" == X'7' ]; then
                DEP_PKGS="${DEP_PKGS} python36-PyMySQL gcc python3-devel openldap-devel"
                DEP_PIP3_MODS="${DEP_PIP3_MODS} python-ldap==3.3.1"
            else
                DEP_PKGS="${DEP_PKGS} python3-ldap python3-PyMySQL"
            fi

        elif [ X"${DISTRO}" == X'DEBIAN' ]; then
            DEP_PKGS="${DEP_PKGS} python3-pymysql"

            if [ X"${DISTRO_VERSION}" == X'9' ]; then
                DEP_PKGS="${DEP_PKGS} python3-pyldap"
            else
                DEP_PKGS="${DEP_PKGS} python3-ldap"
            fi
        fi

        [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-ldap python3-pymysql"
        [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} net/py-ldap databases/py-pymysql"
        [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-ldap py3-mysqlclient"
    fi

elif grep '^backend' ${IREDAPD_CONF_PY} | grep 'mysql' &>/dev/null; then
    # MySQL/MariaDB backend
    export IREDMAIL_BACKEND='MYSQL'

    if [ X"$(has_python_module pymysql)" == X'NO' ]; then
        if [ X"${DISTRO}" == X'RHEL' ]; then
            if [ X"${DISTRO_VERSION}" == X'7' ]; then
                DEP_PKGS="${DEP_PKGS} python36-PyMySQL"
            else
                DEP_PKGS="${DEP_PKGS} python3-PyMySQL"
            fi
        fi

        [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-pymysql"
        [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-pymysql"
        [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} databases/py-pymysql"
        if [ X"${DISTRO}" == X'OPENBSD' ]; then
            if [ X"${DISTRO_VERSION}" == X'6.8' ]; then
                DEP_PKGS="${DEP_PKGS} py3-pymysql"
            fi
        fi
    fi

    if [ X"${DISTRO}" == X'OPENBSD' ]; then
        if [ X"${DISTRO_VERSION}" == X'6.6' -o X"${DISTRO_VERSION}" == X'6.7' ]; then
            if [ X"$(has_python_module MySQLdb)" == X'NO' ]; then
                DEP_PKGS="${DEP_PKGS} py3-mysqlclient"
            fi
        fi
    fi

elif grep '^backend' ${IREDAPD_CONF_PY} | grep 'pgsql' &>/dev/null; then
    # PostgreSQL backend
    export IREDMAIL_BACKEND='PGSQL'

    if [ X"$(has_python_module psycopg2)" == X'NO' ]; then
        if [ X"${DISTRO}" == X'RHEL' ]; then
            if [ X"${DISTRO_VERSION}" == X'7' ]; then
                DEP_PKGS="${DEP_PKGS} python36-psycopg2"
            else
                DEP_PKGS="${DEP_PKGS} python3-psycopg2"
            fi
        fi

        [ X"${DISTRO}" == X'DEBIAN' ]   && DEP_PKGS="${DEP_PKGS} python3-psycopg2"
        [ X"${DISTRO}" == X'UBUNTU' ]   && DEP_PKGS="${DEP_PKGS} python3-psycopg2"
        [ X"${DISTRO}" == X'FREEBSD' ]  && DEP_PKGS="${DEP_PKGS} databases/py-psycopg2"
        [ X"${DISTRO}" == X'OPENBSD' ]  && DEP_PKGS="${DEP_PKGS} py3-psycopg2"
    fi
fi

if [ X"${DEP_PKGS}" != X'' ]; then
    install_pkgs ${DEP_PKGS}
fi

if [ X"${DEP_PIP3_MODS}" != X'' ]; then
    ${CMD_PIP3} install -U ${DEP_PIP3_MODS}
fi

# Re-check py3 and create symbol link.
if [ X"${DISTRO}" == X'OPENBSD' ]; then
    for v in 3.8 3.7; do
        if [ -x /usr/local/bin/python${v} ]; then
            ln -sf /usr/local/bin/python${v} /usr/local/bin/python3
            break
        fi
    done

    for v in 3.8 3.7; do
        if [ -x /usr/local/bin/pip${v} ]; then
            ln -sf /usr/local/bin/pip${v} /usr/local/bin/pip3
            break
        fi
    done
fi

if [ ! -x ${CMD_PYTHON3} ]; then
    echo "<<< ERROR >>> Failed to install Python 3, please install it manually."
    exit 255
fi

if [ ! -x ${CMD_PIP3} ]; then
    echo "<<< ERROR >>> Failed to install pip for Python 3, please install it manually."
    exit 255
fi

if [ -L ${IREDAPD_ROOT_DIR} ]; then
    export IREDAPD_ROOT_REAL_DIR="$(readlink ${IREDAPD_ROOT_DIR})"
    echo "* Found iRedAPD directory: ${IREDAPD_ROOT_DIR}, symbol link of ${IREDAPD_ROOT_REAL_DIR}"
else
    echo "<<< ERROR >>> Directory is not a symbol link created by iRedMail. Exit."
    exit 255
fi

# Detect config file
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
if ! echo ${ROOTDIR} | grep 'iRedAPD.*/tools' >/dev/null; then
    echo "<<< ERROR >>> Cannot find new version of iRedAPD in current directory. Exit."
    exit 255
fi

mkdir /tmp/iredapd/ 2>/dev/null
cp -f ${ROOTDIR}/../SQL/*sql /tmp/iredapd
chmod -R 0555 /tmp/iredapd

#
# Require SQL root password to create `iredapd` database.
#
export IREDAPD_DB_NAME='iredapd'
if ! grep '^iredapd_db_' ${IREDAPD_CONF_PY} &>/dev/null; then
    export IREDAPD_DB_SERVER='127.0.0.1'
    export IREDAPD_DB_USER='iredapd'
    export IREDAPD_DB_PASSWD="$(${RANDOM_STRING})"

    mkdir /tmp/iredapd/ 2>/dev/null
    cp -f ${ROOTDIR}/../SQL/*sql /tmp/iredapd
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

add_new_pgsql_tables()
{
    # Usage: add_new_pgsql_tables <sql-file-name> "SELECT ..."

    # name of SQL file under SQL/update/
    sql_file="$1"
    shift 1

    # SQL statement used to verify whether it's necessary to import the SQL file.
    sql_statement="$@"

    ${psql_conn} -c "${sql_statement}" &>/dev/null

    if [ X"$?" != X'0' ]; then
        cp ${ROOTDIR}/../SQL/update/${sql_file} /tmp/
        chmod 0555 /tmp/${sql_file}
        ${psql_conn} -c "\i /tmp/${sql_file}"
        rm -f /tmp/${sql_file}
    fi
}


if egrep '^backend.*(mysql|ldap)' ${IREDAPD_CONF_PY} &>/dev/null; then
    cp -f ${ROOTDIR}/../SQL/iredapd.mysql /tmp/

    existing_sql_tables="$(${mysql_conn} -e "show tables")"

    echo "* Add new SQL tables - if there's any"
    ${mysql_conn} -e "SOURCE /tmp/iredapd.mysql"

    #
    # `greylisting_whitelist_domains`
    #
    echo "${existing_sql_tables}" | grep '\<greylisting_whitelist_domains\>' &>/dev/null
    if [ X"$?" != X'0' ]; then
        cp -f ${ROOTDIR}/../SQL/greylisting_whitelist_domains.sql /tmp/
        chmod 0555 /tmp/greylisting_whitelist_domains.sql
        ${mysql_conn} -e "SOURCE /tmp/greylisting_whitelist_domains.sql"
        rm -f /tmp/greylisting_whitelist_domains.sql &>/dev/null
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
    # `wblist_rdns`
    #
    echo "${existing_sql_tables}" | grep '\<wblist_rdns\>' &>/dev/null
    if [ X"$?" != X'0' ]; then
        cp -f ${ROOTDIR}/../SQL/wblist_rdns.sql /tmp/
        chmod 0555 /tmp/wblist_rdns.sql
        ${mysql_conn} -e "SOURCE /tmp/wblist_rdns.sql"
        rm -f /tmp/wblist_rdns.sql &>/dev/null
    fi

    #
    # iRedAPD-2.3: new column `throttle_tracking.last_notify_time`
    #
    (${mysql_conn} <<EOF
DESC throttle_tracking;
EOF
) | grep 'last_notify_time' &>/dev/null

    if [ X"$?" != X'0' ]; then
        ${mysql_conn} <<EOF
ALTER TABLE throttle_tracking ADD COLUMN last_notify_time INT(10) UNSIGNED NOT NULL DEFAULT 0;
EOF
    fi

elif egrep '^backend.*pgsql' ${IREDAPD_CONF_PY} &>/dev/null; then
    export PGPASSWORD="${iredapd_db_password}"

    # v1.8: greylisting_whitelist_domains
    add_new_pgsql_tables 1.8-greylisting_whitelist_domains.pgsql "SELECT id FROM greylisting_whitelist_domains LIMIT 1"

    # v2.1: `greylisting_whitelist_domain_spf`, `wblist_rdns`
    add_new_pgsql_tables 2.1-greylisting_whitelist_domain_spf.pgsql "SELECT id FROM greylisting_whitelist_domain_spf LIMIT 1"
    add_new_pgsql_tables 2.1-wblist_rdns.pgsql "SELECT id FROM wblist_rdns LIMIT 1"

    #
    # INDEX on `greylisting_tracking`: (client_address, passed)
    #
    ${psql_conn} -c "SELECT indexname FROM pg_indexes WHERE indexname='idx_greylisting_tracking_client_address_passed'" | grep 'idx_greylisting_tracking_client_address_passed' &>/dev/null

    if [ X"$?" != X'0' ]; then
        ${psql_conn} -c "CREATE INDEX idx_greylisting_tracking_client_address_passed ON greylisting_tracking (client_address, passed);"
    fi

    #
    # v2.3: new column `throttle_tracking.last_notify_time`
    #
    ${psql_conn} -c "\d+ throttle_tracking" | grep 'last_notify_time' &>/dev/null
    if [ X"$?" != X'0' ]; then
        ${psql_conn} -c "ALTER TABLE throttle_tracking ADD COLUMN last_notify_time BIGINT NOT NULL DEFAULT 0;"
    fi

    # v2.5: `srs_exclude_domains`
    add_new_pgsql_tables 2.5-srs_exclude_domains.pgsql "SELECT id FROM srs_exclude_domains LIMIT 1"

    # v3.2: `senderscore_cache`, `smtp_sessions`
    add_new_pgsql_tables 3.2-senderscore_cache.pgsql "SELECT client_address FROM senderscore_cache LIMIT 1"
    add_new_pgsql_tables 3.2-smtp_sessions.pgsql "SELECT client_address FROM smtp_sessions LIMIT 1"
fi

#
# Upgrade to new version
#
# Copy current directory to web DocumentRoot
dir_new_version="$(dirname ${ROOTDIR})"
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

# Set correct SQL driver for SQLAlchemy. Defaults to `MySQLdb`.
if [ X"${IREDMAIL_BACKEND}" == X"OPENLDAP" -o X"${IREDMAIL_BACKEND}" == X'MYSQL' ]; then
    # OpenBSD 6.7 and earlier releases doesn't have binary package `py3-pymysql`.
    if [ X"${DISTRO}" == X'OPENBSD' ]; then
        if [ X"${DISTRO_VERSION}" == X'6.8' ]; then
            export SQL_DB_DRIVER='pymysql'
        fi
    else
        export SQL_DB_DRIVER='pymysql'
    fi

    if [ X"${SQL_DB_DRIVER}" != X'' ]; then
        if ! grep '^SQL_DB_DRIVER' ${NEW_IREDAPD_CONF} &>/dev/null; then
            echo "" >> ${NEW_IREDAPD_CONF}
            echo "SQL_DB_DRIVER = '${SQL_DB_DRIVER}'" >> ${NEW_IREDAPD_CONF}
        fi
    fi
fi

echo "* Set correct owner and permission for ${NEW_IREDAPD_ROOT_DIR}: ${SYS_USER_ROOT}:${SYS_GROUP_ROOT}, 0500."
chown -R ${SYS_USER_ROOT}:${SYS_GROUP_ROOT} ${NEW_IREDAPD_ROOT_DIR}
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
    export SYSTEMD_SERVICE_DIR2='/etc/systemd/system'
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
        echo "* Remove existing systemd service files."
        rm -f ${SYSTEMD_SERVICE_DIR}/iredapd.service &>/dev/null
        rm -f ${SYSTEMD_SERVICE_DIR2}/iredapd.service &>/dev/null
        rm -f ${SYSTEMD_SERVICE_USER_DIR}/iredapd.service &>/dev/null

        echo "* Copy systemd service file: ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.service -> ${SYSTEMD_SERVICE_DIR}/iredapd.service."
        cp -f ${IREDAPD_ROOT_DIR}/rc_scripts/iredapd.service ${SYSTEMD_SERVICE_DIR}/iredapd.service
        chmod -R 0644 ${SYSTEMD_SERVICE_DIR}/iredapd.service
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

# SRS parameters
if ! grep '^srs_' ${NEW_IREDAPD_CONF} &>/dev/null; then
    # Add required settings.
    add_missing_parameter 'srs_forward_port' "7778"
    add_missing_parameter 'srs_reverse_port' "7779"
    add_missing_parameter 'srs_domain' "${HOSTNAME}"
    add_missing_parameter 'srs_secrets' "['$(${RANDOM_STRING})']"
fi

# mlmmjadmin integration.
if ! grep '^mlmmjadmin_' ${NEW_IREDAPD_CONF} &>/dev/null; then
    add_missing_parameter 'mlmmjadmin_api_endpoint' "http://127.0.0.1:7790/api"

    # Get api token from mlmmjadmin config file.
    token=$(grep '^api_auth_tokens' /opt/mlmmjadmin/settings.py | awk -F"[=\']" '{print $3}' | tr -d '\n')
    add_missing_parameter 'mlmmjadmin_api_auth_token' "${token}"
fi

# On FreeBSD, syslog socket is /var/run/log.
if [ X"${KERNEL_NAME}" == X'FREEBSD' ]; then
    if ! grep '^SYSLOG_SERVER' ${NEW_IREDAPD_CONF} &>/dev/null; then
        add_missing_parameter 'SYSLOG_SERVER' "/var/run/log"
    fi
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

# Remove deprecated plugins.
rm -f ${IREDAPD_ROOT_DIR}/plugins/ldap_amavisd_block_blacklisted_senders.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/ldap_recipient_restrictions.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/sql_user_restrictions.py &>/dev/null
rm -f ${IREDAPD_ROOT_DIR}/plugins/amavisd_message_size_limit.py &>/dev/null

# Rename old plugins
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
touch ${IREDAPD_LOG_FILE}

# Always set correct owner and permission, so that we can rotate the log files.
chown -R ${SYS_USER_SYSLOG}:${SYS_GROUP_SYSLOG} ${IREDAPD_LOG_DIR}
chmod -R 0750 ${IREDAPD_LOG_DIR}

# syslog and log rotation
if [ X"${KERNEL_NAME}" == X'LINUX' ]; then
    # rsyslog
    cp -f ${ROOTDIR}/../samples/rsyslog.d/iredapd.conf ${SYSLOG_CONF_DIR}/1-iredmail-iredapd.conf
    chown ${SYS_USER_ROOT}:${SYS_GROUP_ROOT} ${SYSLOG_CONF_DIR}/1-iredmail-iredapd.conf
    chmod 0644 ${SYSLOG_CONF_DIR}/1-iredmail-iredapd.conf
    service rsyslog restart >/dev/null

    # log rotation
    cp -f ${ROOTDIR}/../samples/logrotate.d/iredapd ${LOGROTATE_DIR}/iredapd
    chmod 0644 ${LOGROTATE_DIR}/iredapd

    if [ -x /sbin/service ]; then
        perl -pi -e 's#/usr/sbin/service#/sbin/service#g' ${LOGROTATE_DIR}/iredapd
    fi
elif [ X"${KERNEL_NAME}" == X'FREEBSD' ]; then
    # syslog
    [[ -d ${SYSLOG_CONF_DIR} ]] || mkdir -p ${SYSLOG_CONF_DIR}
    cp -f ${ROOTDIR}/../samples/freebsd/syslog.d/iredapd.conf ${SYSLOG_CONF_DIR}/iredapd.conf
    chown ${SYS_USER_ROOT}:${SYS_GROUP_ROOT} ${SYSLOG_CONF_DIR}/iredapd.conf
    chmod 0644 ${SYSLOG_CONF_DIR}/iredapd.conf
    service syslogd restart >/dev/null

    # log rotation
    cp -f ${ROOTDIR}/../samples/freebsd/newsyslog.d/iredapd ${LOGROTATE_DIR}/iredapd
    chmod 0644 ${LOGROTATE_DIR}/iredapd
elif [ X"${KERNEL_NAME}" == X'OPENBSD' ]; then
    if ! grep "${IREDAPD_LOG_FILE}" /etc/syslog.conf &>/dev/null; then
        # '!!' means abort further evaluation after first match
        echo '' >> /etc/syslog.conf
        echo '!!iredapd' >> /etc/syslog.conf
        echo "local5.*        ${IREDAPD_LOG_FILE}" >> /etc/syslog.conf
    fi

    if ! grep "${IREDAPD_LOG_FILE}" /etc/newsyslog.conf &>/dev/null; then
        cat >> /etc/newsyslog.conf <<EOF
${IREDAPD_LOG_FILE}    ${SYS_USER_SYSLOG}:${SYS_GROUP_SYSLOG}   600  7     *    24    Z
EOF
    fi
fi

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
1   *   *   *   *   ${CMD_PYTHON3} ${IREDAPD_ROOT_DIR}/tools/cleanup_db.py &>/dev/null
EOF
fi

# cron job for updating IP addresses/networks of greylisting whitelist domains.
#if ! grep 'spf_to_greylist_whitelists.py' ${CRON_FILE_ROOT} &>/dev/null; then
#    cat >> ${CRON_FILE_ROOT} <<EOF
## iRedAPD: Convert specified SPF DNS record of specified domain names to IP
##          addresses/networks every 10 minutes.
#*/30   *   *   *   *   ${CMD_PYTHON3} ${IREDAPD_ROOT_DIR}/tools/spf_to_greylist_whitelists.py &>/dev/null
#EOF
#fi

echo "* Replace py2 by py3 in cron jobs."
perl -pi -e 's#(.*) python (.*/opt/iredapd/tools/.*)#${1} $ENV{CMD_PYTHON3} ${2}#' ${CRON_FILE_ROOT}
perl -pi -e 's#(.*) python2 (.*/opt/iredapd/tools/.*)#${1} $ENV{CMD_PYTHON3} ${2}#' ${CRON_FILE_ROOT}
perl -pi -e 's#(.*)/usr/bin/python (.*/opt/iredapd/tools/.*)#${1}$ENV{CMD_PYTHON3} ${2}#' ${CRON_FILE_ROOT}
perl -pi -e 's#(.*)/usr/bin/python2 (.*/opt/iredapd/tools/.*)#${1}$ENV{CMD_PYTHON3} ${2}#' ${CRON_FILE_ROOT}
perl -pi -e 's#(.*)/usr/local/bin/python (.*/opt/iredapd/tools/.*)#${1}$ENV{CMD_PYTHON3} ${2}#' ${CRON_FILE_ROOT}
perl -pi -e 's#(.*)/usr/local/bin/python2 (.*/opt/iredapd/tools/.*)#${1}$ENV{CMD_PYTHON3} ${2}#' ${CRON_FILE_ROOT}

#------------------------------
# Clean up.
#
rm -rf /tmp/iredapd* &>/dev/null

# Remove `*.pyc` files.
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
