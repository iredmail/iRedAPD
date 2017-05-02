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

modules='test_reject_sender_login_mismatch.py'

retval=0
for mod in ${modules}; do
    pytest $mod

    _retval="$?"
    [ X"${_retval}" == X'0' ]  || retval="${_retval}"
done

# Cleanup sql records used for testing.
[ X"${retval}" == X'0' ] && pytest test_cleanup.py
