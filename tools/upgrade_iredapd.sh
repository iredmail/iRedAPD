#!/usr/bin/env bash

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

export IREDAPD_DAEMON_USER='iredapd'
export IREDAPD_DAEMON_GROUP='iredapd'

# Check OS to detect some necessary info.
export KERNEL_NAME="$(uname -s | tr '[a-z]' '[A-Z]')"
export RC_SCRIPT_NAME='iredapd'

if [ X"${KERNEL_NAME}" == X"LINUX" ]; then
    if [ -f /etc/redhat-release ]; then
        # RHEL/CentOS
        export DISTRO='RHEL'
    elif [ -f /etc/lsb-release ]; then
        # Ubuntu
        export DISTRO='UBUNTU'
    elif [ -f /etc/debian_version ]; then
        # Debian
        export DISTRO='DEBIAN'
    elif [ -f /etc/SuSE-release ]; then
        # openSUSE
        export DISTRO='SUSE'
    else
        echo "<<< ERROR >>> Cannot detect Linux distribution name. Exit."
        echo "Please contact support@iredmail.org to solve it."
        exit 255
    fi
elif [ X"${KERNEL_NAME}" == X'FREEBSD' ]; then
    export DISTRO='FREEBSD'
elif [ X"${KERNEL_NAME}" == X'OPENBSD' ]; then
    export DISTRO='OPENBSD'
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

# Copy config file
if [ -f ${IREDAPD_CONF_PY} ]; then
    echo "* Found iRedAPD config file: ${IREDAPD_CONF_PY}"
    cp ${IREDAPD_CONF_PY} .
elif [ -f ${IREDAPD_CONF_INI} ]; then
    echo "* Found old iRedAPD config file: ${IREDAPD_CONF_INI}, please convert it"
    echo "  to new config format manually."
    exit 255
else
    echo "<<< ERROR >>> Cannot find valid config file (${IRA_CONF_PY})."
    exit 255
fi

# Check whether current directory is iRedAPD
PWD="$(pwd)"
if ! echo ${PWD} | grep 'iRedAPD.*/tools' >/dev/null; then
    echo "<<< ERROR >>> Cannot find new version of iRedAPD in current directory. Exit."
    exit 255
fi

# Copy current directory to Apache server root
dir_new_version="$(dirname ${PWD})"
name_new_version="$(basename ${dir_new_version})"
NEW_IREDAPD_ROOT_DIR="/opt/${name_new_version}"
if [ ! -d ${NEW_IREDAPD_ROOT_DIR} ]; then
    echo "* Create directory ${NEW_IREDAPD_ROOT_DIR}."
    mkdir ${NEW_IREDAPD_ROOT_DIR} &>/dev/null
fi

echo "* Copying new version to ${NEW_IREDAPD_ROOT_DIR}"
cp -rf ${dir_new_version}/* ${NEW_IREDAPD_ROOT_DIR}
cp -p ${IREDAPD_CONF_PY} ${NEW_IREDAPD_ROOT_DIR}/
chown -R ${IREDAPD_DAEMON_USER}:${IREDAPD_DAEMON_GROUP} ${NEW_IREDAPD_ROOT_DIR}
chmod -R 0555 ${NEW_IREDAPD_ROOT_DIR}
chmod 0400 ${IREDAPD_CONF_PY}

echo "* Removing old symbol link ${IREDAPD_ROOT_DIR}"
rm -f ${IREDAPD_ROOT_DIR}

echo "* Creating symbol link ${IREDAPD_ROOT_DIR} to ${NEW_IREDAPD_ROOT_DIR}"
cd /opt && ln -s ${name_new_version} iredapd

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
<<< NOTE >>> iRedAPD log file is /var/log/iredapd.log.
EOF
