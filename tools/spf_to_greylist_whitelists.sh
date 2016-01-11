#!/usr/bin/env bash

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Query SPF DNS record of specified domains and generate SQL
#          file which is used to insert IP addresses of SPF records as
#          whitelisted greylisting senders.

#
# USAGE
#
#   Run command with the mail domain names which you want to avoid gryelisting:
#
#       $ bash spf_to_greylist_whitelists.sh <domain> [domain ...]
#
#   For example:
#
#       $ bash spf_to_greylist_whitelists.sh google.com aol.com
#
#   it will create file:
#
#       /tmp/iredapd-greylisting-whitelist-auto-update.sql
#
#   You'd better review it before importing it to iRedAPD SQL database.
#   If you prefer to import generated SQL file directly, please run it with
#   argument '--import' (it must be FIRST argument). It will read iRedAPD
#   config file (defaults to /opt/iredapd/settings.py) to extract SQL
#   credential and import generated SQL file. e.g.
#
#       $ bash spf_to_greylist_whitelists.sh --import google.com aol.com

#
# Required commands:
#
#   - dig
#   - awk
#   - sed
#   - grep
#   - head
#   - tr

#
# KNOWN ISSUES
#
#   * not supported spf syntax:
#
#       - a/24 a:offsite.example.com/24
#       - mx/24 mx:offsite.example.com/24
#       - exists:<domain>

#
# REFERENCES
#
#   * SPF Record Syntax: http://www.openspf.org/SPF_Record_Syntax

#
# TODO
#
#   - support spf syntax: ptr ptr:<domain>
#   - import generated SQL file directly.

# Specify your preferred DNS server. A local DNS server is better.
# 8.8.8.8 and 8.8.4.4 are Google DNS servers.
#export DNS_SERVER='8.8.8.8'
export DNS_SERVER='223.5.5.5'

# Import generated SQL file directly.
export IREDAPD_CONF='/opt/iredapd/settings.py'
export IMPORT_SQL='NO'
if [ X"${1}" == X'--import' ] ; then
    export IMPORT_SQL='YES'
    shift 1
fi

# Temporary files
# used to store queried domain names
export TMP_QUERIED_DOMAINS="/tmp/iredapd.domains.${RANDOM}${RANDOM}${RANDOM}"
# used to store IP of A/MX/SPF records
export TMP_RETURNED_IPS="/tmp/iredapd.ips.${RANDOM}${RANDOM}${RANDOM}"
# used to store SQL commands
export TMP_SQL="/tmp/iredapd-greylisting-whitelists-auto-update.sql"

# Input string like 'var:value', return 'value'.
get_value_after_colon()
{
    str="${1}"
    value="$(echo ${str} | awk -F':' '{print $2}')"

    echo "${value}"
}

# Remove all single quote and double quotes in string.
strip_quotes()
{
    # Read input from stdin
    str="$(cat <&0)"

    value="$(echo ${str} | sed 's/\"//g' | sed "s/\'//g")"

    echo "${value}"
}

# Use default dns server (DNS_SERVER) or query to find authorized NS servers
# for specified domain (only first one will be used).
query_ns()
{
    if [[ -z ${DNS_SERVER} ]]; then
        domain="${1}"

        # Use local DNS server to query authorized NS server for further query
        NS="$(dig -t NS ${domain} |grep "^${domain}\." | grep 'NS' | awk '{print $NF}' | sed 's/\.$//g' | head -1)"

        if [[ -n ${NS} ]]; then
            ns="${NS}"
        fi
    fi

    echo "${DNS_SERVER}"
}

query_a()
{
    domain="${1}"

    NS="$(query_ns ${domain})"

    records="$(dig @${NS} -t A ${domain} \
        | grep '^${domain}\..*IN.*A.*' \
        | awk '{print $NF}')"

    echo "${records}"
}

# Query IP address(es) of specified MX domain name.
query_mx()
{
    domain="${1}"

    NS="$(query_ns ${domain})"

    mx="$(dig @${NS} -t MX ${domain} \
        | grep '^${domain}\..*IN.*MX.*' \
        | awk '{print $NF}')"

    a=''
    for i in mx; do
        a="${a} $(query_a ${i})"
    done

    echo "${a}"
}

# Query SPF record.
query_spf()
{
    domain="${1}"

    NS="$(query_ns ${domain})"

    spf="$(dig @${NS} -t TXT ${domain} \
        | grep 'v=spf1' \
        | awk -F'"' '{print $2}' \
        | awk -F'v=spf1 ' '{print $2}' \
        | sed 's/redirect=/include:/' \
        | tr '[A-Z]' '[a-z]')"

    echo "${spf}"
}

# Recursively query SPF records of domains listed in 'include:'.
# Usage: query_spf_of_include_domain [domain]
query_spf_of_include_domain()
{
    domain="${1}"

    NS="$(query_ns ${domain})"
    spf="$(query_spf ${domain})"

    echo "${domain}" >> ${TMP_QUERIED_DOMAINS}
    echo "$(parse_spf ${domain} ${spf})"
}

# Parse spf record.
# Usage: parse_spf [domain] [spf]
parse_spf()
{
    domain="${1}"
    shift 1
    spf="$@"

    # Return if no spf record
    if [[ -z ${spf} ]]; then
        echo ''
        return
    fi

    # Collect final IP addresses of SPF records
    ip=''
    # Include A record
    a=''
    # Include MX record
    mx=''

    # Extract 'include:xxx'.
    # Sample: spf of 'google.com': 'include:_spf.google.com ~all'
    included_domains=''

    for r in ${spf}; do
        colon_value="$(get_value_after_colon ${r})"

        if echo ${r} | grep '^include:' &>/dev/null; then
            # 'include:xxx'
            included_domains="${included_domains} ${colon_value}"
        elif echo ${r} | grep '^ip4:' &>/dev/null; then
            # 'ip4:xxx'
            ip="${ip} ${colon_value}"
        elif echo ${r} | grep '^ip6:' &>/dev/null; then
            # 'ip4:xxx', 'ip6:xxx'
            _ip6="$(echo ${r} | sed 's/^ip6://')"
            ip="${ip} ${_ip6}"
        elif echo ${r} | grep '^a:' &>/dev/null; then
            # 'a:xxx'
            a="${a} ${colon_value}"
        elif echo ${r} | grep '^mx:' &>/dev/null; then
            # 'mx:xxx'
            mx="${mx} ${colon_value}"
        elif [ X"${r}" == X'a' ]; then
            # Add A record of domain
            a="${a} ${domain}"
        elif [ X"${r}" == X'mx' ]; then
            # Add MX record of domain
            mx="${mx} ${domain}"
        fi
    done

    # Find IP of included domains
    if [[ -n ${included_domains} ]]; then
        for domain in ${included_domains}; do
            ip="${ip} $(query_spf_of_include_domain ${domain})"
        done
    fi

    if [[ -n ${mx} ]]; then
        for i in ${mx}; do
            ip="${ip} $(query_mx ${mx})"
        done
    fi

    echo "${ip}"
}

domains="$@"

# Create temporary files.
rm -f ${TMP_QUERIED_DOMAINS} ${TMP_RETURNED_IPS} ${TMP_SQL} &>/dev/null
touch ${TMP_QUERIED_DOMAINS} ${TMP_RETURNED_IPS} ${TMP_SQL} &>/dev/null

for domain in ${domains}; do
    # Convert domain name to lower cases.
    domain="$(echo ${domain} | tr '[A-Z]' '[a-z]')"

    echo "* Processing domain: ${domain}"

    # Make sure we're checking new domain to avoid infinitely loop
    regx="$(echo ${domain} | sed 's/\./\\./g')"
    if grep "^${regx}$" ${TMP_QUERIED_DOMAINS} &>/dev/null; then
        continue
    fi

    # Query SPF record
    spf="$(query_spf ${domain})"

    # Parse returned SPF record
    ips="$(parse_spf ${domain} ${spf})"

    # Delete old records if the query returned new IP addresses.
    if echo ${ips} | grep '\.' &>/dev/null; then
        echo "DELETE FROM greylisting_whitelists WHERE comment='AUTO-UPDATE: ${domain}';" >> ${TMP_SQL}
    fi

    for ip in ${ips}; do
        # Avoid duplicate IP/network
        regx="$(echo ${ip} | sed 's/\./\\./g')"
        if grep "^${regx}$" ${TMP_RETURNED_IPS} &>/dev/null; then
            continue
        fi

        echo "INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '${ip}', 'AUTO-UPDATE: ${domain}');" >> ${TMP_SQL}

        echo "${ip}" >> ${TMP_RETURNED_IPS}
    done

    echo "${domain}" >> ${TMP_QUERIED_DOMAINS}
done

# Remove temporary files.
rm -f ${TMP_QUERIED_DOMAINS} ${TMP_RETURNED_IPS} &>/dev/null

# Extract SQL username/password from iRedAPD config file to import SQL file
if [ X"${IMPORT_SQL}" == X'YES' ]; then
    if [[ ! -f ${IREDAPD_CONF} ]]; then
        echo "* <<< ERROR >>> iRedAPD config file ${IREDAPD_CONF} doesn't exist, not importing SQL file. Abort."
        exit 255
    fi

    iredapd_db_server="$(grep '^iredapd_db_server' ${IREDAPD_CONF} | awk '{print $NF}' | strip_quotes)"
    iredapd_db_port="$(grep '^iredapd_db_port' ${IREDAPD_CONF} | awk '{print $NF}' | strip_quotes)"
    iredapd_db_name="$(grep '^iredapd_db_name' ${IREDAPD_CONF} | awk '{print $NF}' | strip_quotes)"
    iredapd_db_user="$(grep '^iredapd_db_user' ${IREDAPD_CONF} | awk '{print $NF}' | strip_quotes)"
    iredapd_db_password="$(grep '^iredapd_db_password' ${IREDAPD_CONF} | awk '{print $NF}' | strip_quotes)"

    # Get backend
    backend="$(grep '^backend' ${IREDAPD_CONF} | awk '{print $NF}' | strip_quotes)"

    if [ X"${backend}" == X'pgsql' ]; then
        # PostgreSQL: Import with `psql`
        :
    else
        # MySQL: Import with `mysql`
        set -x
        echo "* Importing SQL file ..."
        mysql -h${iredapd_db_server} \
              -p${iredapd_db_port} \
              -u${iredapd_db_user} \
              -p${iredapd_db_password} \
              ${iredapd_db_name} \
              -e "SOURCE ${TMP_SQL}"
        echo "* [DONE] Imported."

        echo "* Removing SQL file ..."
        rm -f ${TMP_SQL} &>/dev/null
        set +x
    fi
else
    echo "* Please review file ${TMP_SQL} before importing it to iRedAPD database."
fi
