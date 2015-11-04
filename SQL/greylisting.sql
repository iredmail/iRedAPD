-- greylisting settings.
--
-- `period`: TODO
-- `priority`: large number has higher priority. Default priorities:
--
--      email       -> 50   # <- e.g. 'user@domain.com'. Highest priority
--      ip          -> 40   # <- e.g. 173.254.22.21
--      network     -> 30   # <- e.g. 173.254.22/24
--      domain      -> 20   # <- e.g. @domain.com
--      subdomain   -> 10   # <- e.g. @.domain.com
--      catchall    ->  0   # <- '@.'. Lowest priority
--
-- `enable`: enable or disable greylisting
--
-- Query greylisting setting with sorted priority:
--
--  sql> SELECT enable FROM greylisting
--          WHERE sender IN (email, ip, domain, subdomain, catchall)
--          ORDER BY priority DESC;
--
-- Sample settings (`sender`, `domain`, `priority`):
--
--  - per-sender-email setting: ('user@domain.com', 'domain.com', 50)
--  - per-sender-domain setting: ('domain.com', 'domain.com', 20)
--  - per-sender-subdomain setting: ('@.domain.com', 'domain.com', 10)
--  - Global setting: ('@.', '', 0)

CREATE TABLE IF NOT EXISTS `greylisting` (
    `id`        BIGINT(20) UNSIGNED AUTO_INCREMENT,
    `sender`    VARCHAR(255) NOT NULL DEFAULT '',
    `domain`    VARCHAR(255) NOT NULL DEFAULT '',
    `priority`  TINYINT(2) NOT NULL DEFAULT 0,
    `enable`    TINYINT(1) NOT NULL DEFAULT 1,
    `comment`   TEXT,

    PRIMARY KEY (`id`),
    UNIQUE INDEX (`sender`, `enable`),
    INDEX (domain),
    INDEX (priority)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS `greylisting_whitelists` (
    `id`        BIGINT(20) UNSIGNED AUTO_INCREMENT,
    `source`    VARCHAR(255) NOT NULL DEFAULT '',
    `comment`   TEXT,

    PRIMARY KEY (`id`),
    UNIQUE INDEX (`source`)
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
