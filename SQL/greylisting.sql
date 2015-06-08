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
    `sender` VARCHAR(255) NOT NULL DEFAULT '',
    `domain` VARCHAR(255) NOT NULL DEFAULT '',
    `priority` TINYINT(2) NOT NULL DEFAULT 0,
    `enable` TINYINT(1) NOT NULL DEFAULT 1,
    `comment` TEXT,
    PRIMARY KEY  (`sender`, `enable`),
    INDEX (domain),
    INDEX (priority)
) ENGINE=MyISAM;


-- Stores all smtp sessions. old records should be removed with a cron job.
/*
CREATE TABLE IF NOT EXISTS `greylisting_sessions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `date` datetime NOT NULL default '0000-00-00 00:00:00',
  -- Timestamp
  `mailto` varchar(255) NOT NULL default '',
  `mailfrom` varchar(255) NOT NULL default '',
  `host` varchar(255) NOT NULL default '',
  `result` varchar(255) NOT NULL default '',
  PRIMARY KEY  (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1 AUTO_INCREMENT=1311220 ;
*/
