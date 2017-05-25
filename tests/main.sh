#!/usr/bin/env bash

tmprootdir="$(dirname $0)"
echo ${tmprootdir} | grep '^/' >/dev/null 2>&1
if [ X"$?" == X"0" ]; then
    export ROOTDIR="${tmprootdir}"
else
    export ROOTDIR="$(pwd)"
fi

# Make sure custom config file exists.
touch ${ROOTDIR}/tsettings.py

plugins="
    reject_null_sender
    reject_sender_login_mismatch
    wblist_rdns
    sql_alias_access_policy
"

# Add custom settings
echo 'log_level = "debug"   # unittest' >> /opt/iredapd/settings.py
echo 'ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = True     # unittest' >> /opt/iredapd/settings.py

for p in ${plugins}; do
    echo "plugins = ['${p}'] # unittest" >> /opt/iredapd/settings.py

    systemctl daemon-reload &>/dev/null
    service iredapd restart

    # py.test command line arguments
    #  -s   shortcut for --capture=no.
    #  -x   exit instantly on first error or failed test.
    py.test -s -x test_${p}.py
done

# Cleanup SQL records generated during testing
py.test test_cleanup.py

# Remove custom settings
perl -pi -e 's#.*unittest##g' /opt/iredapd/settings.py

# Remove all trailing blank lines at end of file (only).
sed -i -e :a -e '/^\n*$/{$d;N;};/\n$/ba' /opt/iredapd/settings.py
