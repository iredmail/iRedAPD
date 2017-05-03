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

modules="
    test_reject_null_sender.py
    test_reject_sender_login_mismatch.py
    test_cleanup.py
"

pytest ${modules}
