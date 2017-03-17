-- Throttling.
-- Please check iRedAPD plugin throttle for more details.
CREATE TABLE throttle (
    id          SERIAL PRIMARY KEY,
    account     VARCHAR(255)            NOT NULL,

    -- outbound: sender throttling
    -- inbound: recipient throttling
    kind        VARCHAR(10)             NOT NULL DEFAULT 'outbound',

    priority    BIGINT                NOT NULL DEFAULT 0,
    period      BIGINT                NOT NULL DEFAULT 0, -- Peroid, in seconds.

    -- throttle settings.
    --  * set value to -1 to force check setting with lower priority
    --  * set value to 0 to unlimited, and stop checking settings with lower priority.
    msg_size    BIGINT                  NOT NULL DEFAULT -1, -- Limit of single (received) message size, in bytes.
    max_msgs    BIGINT                  NOT NULL DEFAULT -1, -- Number of max (received) messages in total.
    max_quota   BIGINT                  NOT NULL DEFAULT -1 -- Number of current (received) messages.
);

CREATE INDEX idx_account ON throttle (account);

-- Track per-user throttle.
CREATE TABLE throttle_tracking (
    id SERIAL PRIMARY KEY,
    -- foreign key of throttle.id
    tid         BIGINT                  REFERENCES throttle(id),
    -- tracking account. e.g. user@domain, @domain, '@.'.
    account     VARCHAR(255)            NOT NULL DEFAULT '',    -- Sender or recipient

    -- Used while cleaning up old tracking records
    period      BIGINT                NOT NULL DEFAULT 0, -- Peroid, in seconds.

    -- Track accumulated msgs/quota since init tracking.
    cur_msgs    BIGINT   NOT NULL DEFAULT 0, -- Number of current messages.
    cur_quota   BIGINT        NOT NULL DEFAULT 0, -- Current accumulated message size in total, in bytes.

    -- Track initial and last tracking time
    init_time   BIGINT NOT NULL DEFAULT 0, -- The time we initial the throttling.
    last_time   BIGINT NOT NULL DEFAULT 0 -- The time we last track the throttling.
);

CREATE INDEX idx_tid_account ON throttle_tracking (tid, account);

-- greylisting settings.
--
--             ----------------------------------
-- `priority`: larger number has higher priority. Default priorities are
--             ----------------------------------
--             defined in libs/__init__.py.
--
-- `sender_priority` has same syntax/value as priority.
--
-- `account`: local recipient address. Valid account formats:
--
--      user@domain.com: full email address
--      @domain.com: full domain name (with a '@' prefix)
--      @.: catchall
--
-- `active`: greylisting is enabled or disabled.
--
-- Sample settings:
--
--  *) enable server-wide greylisting:
--
--      INSERT INTO greylisting (account, sender, priority, sender_priority, active)
--                       VALUES ('@.', '@.', 0, 0, 1);
--
--     to disable server-wide greylisting, just set active=0.
--
--  *) disable greylisting for one domain:
--
--      INSERT INTO greylisting (account, sender, priority, sender_priority, active)
--                       VALUES ('@mydomain.com', '@.', 20, 0, 0);
--
--  *) disable greylisting for one user:
--
--      INSERT INTO greylisting (account, sender, priority, sender_priority, active)
--                       VALUES ('user@mydomain.com', '@.', 50, 0, 0);
--
--  *) Additional per-domain or per-user greylisting setting:
--
--      *) Don't apply greylisting on sender '8.8.8.8':
--
--          INSERT INTO greylisting (account, sender, priority, sender_priority, active)
--                           VALUES ('@mydomain.com', '8.8.8.8', 20, 40, 0);
--
--          INSERT INTO greylisting (account, sender, priority, sender_priority, active)
--                           VALUES ('user@mydomain.com', '8.8.8.8', 50, 40, 0);
--
CREATE TABLE greylisting (
    id          SERIAL PRIMARY KEY,
    account     VARCHAR(255) NOT NULL DEFAULT '',
    priority    SMALLINT NOT NULL DEFAULT 0,

    sender      VARCHAR(255) NOT NULL DEFAULT '',
    sender_priority  SMALLINT NOT NULL DEFAULT 0,

    comment     VARCHAR(255) NOT NULL DEFAULT '',

    -- enable or disable greylisting
    active      SMALLINT NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX idx_greylisting_account_sender ON greylisting (account, sender);
CREATE INDEX idx_greylisting_comment ON greylisting (comment);

-- Enable greylisting by default.
-- INSERT INTO greylisting (account, priority, sender, sender_priority, active) VALUES ('@.', 0, '@.', 0, 1);

CREATE TABLE greylisting_whitelists (
    id      SERIAL PRIMARY KEY,
    account VARCHAR(255)    NOT NULL DEFAULT '',
    sender  VARCHAR(255)    NOT NULL DEFAULT '',
    comment VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelists_account_sender ON greylisting_whitelists (account, sender);
CREATE INDEX idx_greylisting_whitelists_comment ON greylisting_whitelists (comment);

-- Store mail domain names which you want to disable greylisting for their
-- mail servers.
--
-- Note: these domain names are not used by iRedAPD directly, you need to setup
--       a daily cron job to run 'tools/spf_to_greylisting_whitelists.sh' to
CREATE TABLE greylisting_whitelist_domains (
    id          SERIAL PRIMARY KEY,
    domain      VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelist_domains_domain ON greylisting_whitelist_domains (domain);

-- 'tools/spf_to_greylisting_whitelists.py' will query SPF/MX DNS records of
-- domains stored in SQL table 'greylisting_whitelist_domains', and store the
-- IP/networks listed in SPF/MX in 'greylisting_whitelist_domain_spf', this
-- way we don't mix whitelists managed by domain admins.
CREATE TABLE greylisting_whitelist_domain_spf (
    id      SERIAL PRIMARY KEY,
    account VARCHAR(255)    NOT NULL DEFAULT '',
    sender  VARCHAR(255)    NOT NULL DEFAULT '',
    comment VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelist_domain_spf_account_sender ON greylisting_whitelist_domain_spf (account, sender);
CREATE INDEX idx_greylisting_whitelist_domain_spf_comment ON greylisting_whitelist_domain_spf (comment);

-- Track smtp session for greylisting.
-- Old records should be removed with a cron job.
CREATE TABLE greylisting_tracking (
    id              SERIAL PRIMARY KEY,
    sender          VARCHAR(255) NOT NULL,
    recipient       VARCHAR(255) NOT NULL,
    client_address  VARCHAR(40) NOT NULL,

    sender_domain   VARCHAR(255) NOT NULL DEFAULT '',
    rcpt_domain     VARCHAR(255) NOT NULL DEFAULT '',

    -- The time that the triplet was first seen (record create time)
    init_time       BIGINT NOT NULL DEFAULT 0,
    -- last_time    BIGINT NOT NULL DEFAULT 0,

    -- The time that the blocking of this triplet will expire
    block_expired   BIGINT NOT NULL DEFAULT 0,

    -- The time that the record itself will expire (for aging old records)
    record_expired  BIGINT NOT NULL DEFAULT 0,

    -- The number of delivery attempts that have been blocked
    blocked_count   BIGINT NOT NULL DEFAULT 0,

    -- The number of emails we have sucessfully passed
    -- blocked_count BIGINT NOT NULL DEFAULT 0,

    -- Mark this triplet passes greylisting.
    passed          SMALLINT NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX idx_greylisting_tracking_key    ON greylisting_tracking (sender, recipient, client_address);
CREATE INDEX idx_greylisting_tracking_sender_domain ON greylisting_tracking (sender_domain);
CREATE INDEX idx_greylisting_tracking_rcpt_domain   ON greylisting_tracking (rcpt_domain);
CREATE INDEX idx_greylisting_tracking_client_address_passed ON greylisting_tracking (client_address, passed);
