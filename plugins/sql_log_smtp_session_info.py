# Author: Zhang Huangbin <zhb _at_ iredmail.org>
# Date: 2013-04-20
# Purpose: Log basic info of each smtp session during protocol_state=RCPT.

"""
CREATE TABLE `clients` (
    `id` INT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
    `sender` VARCHAR(255) NOT NULL DEFAULT '',
    `rcpt` VARCHAR(255) NOT NULL DEFAULT '',
    `sender_domain` VARCHAR(255) NOT NULL DEFAULT '',
    `rcpt_domain` VARCHAR(255) NOT NULL DEFAULT '',
    `helo` VARCHAR(255) NOT NULL DEFAULT '',
    -- IPv4 address will be stored by using SQL: INET_ATON('xx.xx.xx.xx')
    -- You can unpack it with SQL: INET_NTOA('xxxxxxxx')
    `ip` INT(10) UNSIGNED NOT NULL DEFAULT 0,
    `day` date NOT NULL DEFAULT '0000-00-00',
    PRIMARY KEY(`id`),
    INDEX (`sender`),
    INDEX (`rcpt`),
    INDEX (`sender_domain`),
    INDEX (`rcpt_domain`),
    INDEX (`helo`),
    INDEX (`ip`),
    INDEX (`day`)
)
"""

import logging
from libs import SMTP_ACTIONS


def restriction(**kwargs):
    conn = kwargs['conn_vmail']
    smtp_session_data = kwargs['smtp_session_data']

    try:
        sql_vars = {'sender': kwargs['sender'],
                'rcpt': kwargs['recipient'],
                'sender_domain': kwargs['sender_domain'],
                'rcpt_domain': kwargs['recipient_domain'],
                'helo': smtp_session_data.get('helo_name', ''),
                'ip': smtp_session_data.get('client_address', '0'),
                }

        sql = """INSERT INTO clients (sender, rcpt, sender_domain, rcpt_domain, helo, ip, day)
                 VALUES ('%(sender)s',
                         '%(rcpt)s',
                         '%(sender_domain)s',
                         '%(rcpt_domain)s',
                         '%(helo)s',
                         INET_ATON('%(ip)s'),
                         NOW());
        """ % sql_vars

        logging.debug(sql)
        conn.execute(sql)
    except Exception, e:
        logging.error(str(e))

    return SMTP_ACTIONS['default']
