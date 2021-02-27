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
    -- msg_size: single message size (in bytes)
    msg_size    BIGINT                  NOT NULL DEFAULT -1,
    -- max_msgs: accumulate max messages in total
    max_msgs    BIGINT                  NOT NULL DEFAULT -1,
    -- max_quota: accumulate message size in total (in bytes)
    max_quota   BIGINT                  NOT NULL DEFAULT -1,
    -- max_rcpts: max recipients in one message.
    max_rcpts   BIGINT                  NOT NULL DEFAULT -1
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
    last_time   BIGINT NOT NULL DEFAULT 0, -- The time we last track the throttling.
    -- the last time we sent notification email to postmaster when user
    -- exceeded throttle setting
    last_notify_time   BIGINT NOT NULL DEFAULT 0
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

CREATE TABLE wblist_rdns (
    id      SERIAL PRIMARY KEY,
    rdns    VARCHAR(255) NOT NULL DEFAULT '',   -- reverse DNS name of sender IP address
    wb      VARCHAR(10) NOT NULL DEFAULT 'B'    -- W=whitelist, B=blacklist
);
CREATE UNIQUE INDEX idx_wblist_rdns_rdns ON wblist_rdns (rdns);
CREATE INDEX idx_wblist_rdns_wb ON wblist_rdns (wb);

CREATE TABLE srs_exclude_domains (
    id      SERIAL PRIMARY KEY,
    domain  VARCHAR(255) NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX idx_srs_exclude_domains_domain ON srs_exclude_domains (domain);


CREATE TABLE senderscore_cache (
    client_address  VARCHAR(40) NOT NULL DEFAULT '',
    score           INT DEFAULT 0,  -- score: 1-100.
    time            BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (client_address)
);
CREATE INDEX idx_senderscore_cache_score ON senderscore_cache (score);
CREATE INDEX idx_senderscore_cache_time ON senderscore_cache (time);


-- Log smtp sessions processed by iRedAPD.
CREATE TABLE smtp_sessions (
    id      SERIAL PRIMARY KEY,
    time    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    time_num    BIGINT NOT NULL DEFAULT 0,
    -- `action` and `reason` returned by plugins
    action                VARCHAR(20) NOT NULL DEFAULT '',
    reason                VARCHAR(255) NOT NULL DEFAULT '',
    -- smtp session info
    instance              VARCHAR(40) NOT NULL DEFAULT '',
    client_address        VARCHAR(40) NOT NULL DEFAULT '',
    client_name           VARCHAR(255) NOT NULL DEFAULT '',
    reverse_client_name   VARCHAR(255) NOT NULL DEFAULT '',
    helo_name             VARCHAR(255) NOT NULL DEFAULT '',
    sender                VARCHAR(255) NOT NULL DEFAULT '',
    sender_domain         VARCHAR(255) NOT NULL DEFAULT '',
    sasl_username         VARCHAR(255) NOT NULL DEFAULT '',
    sasl_domain           VARCHAR(255) NOT NULL DEFAULT '',
    recipient             VARCHAR(255) NOT NULL DEFAULT '',
    recipient_domain      VARCHAR(255) NOT NULL DEFAULT '',
    encryption_protocol   VARCHAR(20) NOT NULL DEFAULT '',
    encryption_cipher     VARCHAR(50) NOT NULL DEFAULT '',
    -- Postfix-3.x logs `server_address` and `server_port`
    server_address        VARCHAR(40) NOT NULL DEFAULT '',
    server_port           VARCHAR(10) NOT NULL DEFAULT ''
);

CREATE INDEX idx_smtp_sessions_time ON smtp_sessions (time);
CREATE INDEX idx_smtp_sessions_time_num ON smtp_sessions (time_num);
CREATE INDEX idx_smtp_sessions_action ON smtp_sessions (action);
CREATE INDEX idx_smtp_sessions_reason ON smtp_sessions (reason);
CREATE INDEX idx_smtp_sessions_instance ON smtp_sessions (instance);
CREATE INDEX idx_smtp_sessions_client_address ON smtp_sessions (client_address);
CREATE INDEX idx_smtp_sessions_client_name ON smtp_sessions (client_name);
CREATE INDEX idx_smtp_sessions_reverse_client_name ON smtp_sessions (reverse_client_name);
CREATE INDEX idx_smtp_sessions_helo_name ON smtp_sessions (helo_name);
CREATE INDEX idx_smtp_sessions_sender ON smtp_sessions (sender);
CREATE INDEX idx_smtp_sessions_sender_domain ON smtp_sessions (sender_domain);
CREATE INDEX idx_smtp_sessions_sasl_username ON smtp_sessions (sasl_username);
CREATE INDEX idx_smtp_sessions_sasl_domain ON smtp_sessions (sasl_domain);
CREATE INDEX idx_smtp_sessions_recipient ON smtp_sessions (recipient);
CREATE INDEX idx_smtp_sessions_recipient_domain ON smtp_sessions (recipient_domain);
CREATE INDEX idx_smtp_sessions_encryption_protocol ON smtp_sessions (encryption_protocol);
CREATE INDEX idx_smtp_sessions_encryption_cipher ON smtp_sessions (encryption_cipher);
CREATE INDEX idx_smtp_sessions_server_address ON smtp_sessions (server_address);
CREATE INDEX idx_smtp_sessions_server_port ON smtp_sessions (server_port);
