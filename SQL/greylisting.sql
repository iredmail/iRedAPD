-- greylisting settings.
--
--             ----------------------------------
-- `priority`: larger number has higher priority. Default priorities:
--             ----------------------------------
--
--      email       -> 50   # <- e.g. 'user@domain.com'. Highest priority
--      ip          -> 40   # <- e.g. 173.254.22.21
--      cidr        -> 30   # <- e.g. 173.254.22.0/24
--      domain      -> 20   # <- e.g. @domain.com
--      subdomain   -> 10   # <- e.g. @.domain.com
--      catchall    ->  0   # <- '@.'. Lowest priority
--
-- `account`: local recipient address. Valid account formats:
--
--      `user@domain.com`: full email address
--      `@domain.com`: full domain name (with a '@' prefix)
--      `@.`: catchall
--
-- `active`: greylisting is enabled or disabled.
--
-- Sample settings:
--
--  *) enable server-wide greylisting:
--
--      INSERT INTO greylisting (account, sender, priority, sender_type, active)
--                       VALUES ('@.', '@.', 0, 'catchall', 1);
--
--     to disable server-wide greylisting, just set active=0.
--
--  *) disable greylisting for one domain:
--
--      INSERT INTO greylisting (account, sender, priority, sender_type, active)
--                       VALUES ('@mydomain.com', '@.', 20, 'catchall', 0);
--
--  *) disable greylisting for one user:
--
--      INSERT INTO greylisting (account, sender, priority, sender_type, active)
--                       VALUES ('user@mydomain.com', '@.', 50, 'catchall', 0);
--
--  *) Additional per-domain or per-user greylisting setting:
--
--      *) Don't apply greylisting on sender '8.8.8.8':
--
--          INSERT INTO greylisting (account, sender, priority, sender_type, active)
--                           VALUES ('@mydomain.com', '8.8.8.8', 20, 'ip', 0);
--
--          INSERT INTO greylisting (account, sender, priority, sender_type, active)
--                           VALUES ('user@mydomain.com', '8.8.8.8', 50, 'ip', 0);
--
CREATE TABLE IF NOT EXISTS `greylisting` (
    `id`        BIGINT(20) UNSIGNED AUTO_INCREMENT,
    `account`   VARCHAR(255) NOT NULL DEFAULT '',
    `sender`    VARCHAR(255) NOT NULL DEFAULT '',
    `priority`  TINYINT(2) NOT NULL DEFAULT 0,

    -- Type of sender: email, ip, cidr, domain, subdomain, catchall
    `sender_type`   VARCHAR(20) NOT NULL DEFAULT '',

    `comment`   TEXT,

    -- enable or disable greylisting
    `active` TINYINT(1) NOT NULL DEFAULT 1,

    PRIMARY KEY (`id`),
    INDEX (`account`),
    INDEX (`sender`),
    UNIQUE INDEX (`account`, `sender`),
    INDEX (`priority`),
    INDEX (`active`)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS `greylisting_whitelists` (
    `id`        BIGINT(20)      UNSIGNED AUTO_INCREMENT,
    `account`   VARCHAR(255)    NOT NULL DEFAULT '',
    `sender`    VARCHAR(255)    NOT NULL DEFAULT '',
    `comment`   TEXT,

    PRIMARY KEY (`id`),
    INDEX (`account`),
    INDEX (`sender`)
) ENGINE=InnoDB;

-- Stores all smtp sessions. old records should be removed with a cron job.
/*
CREATE TABLE IF NOT EXISTS `greylisting_tracking` (
    `id`        BIGINT(20)  UNSIGNED AUTO_INCREMENT,
    `date`      DATETIME    NOT NULL,
    -- Timestamp
    `mailto`    VARCHAR(255) NOT NULL DEFAULT '',
    `mailfrom`  VARCHAR(255) NOT NULL DEFAULT '',
    `host`      VARCHAR(255) NOT NULL DEFAULT '',
    `result`    VARCHAR(255) NOT NULL DEFAULT '',
    PRIMARY KEY  (`id`)
) ENGINE=InnoDB;
*/
