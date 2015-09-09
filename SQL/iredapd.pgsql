-- Throttling.
-- Please check iRedAPD plugin `throttle` for more details.
CREATE TABLE throttle (
    id SERIAL   PRIMARY KEY,
    account     VARCHAR(255)            NOT NULL,

    -- outbound: sender throttling
    -- inbound: recipient throttling
    kind        VARCHAR(10)             NOT NULL DEFAULT 'outbound',

    priority    SMALLINT                NOT NULL DEFAULT 0,
    period      SMALLINT                NOT NULL DEFAULT 0, -- Peroid, in seconds.

    -- throttle settings.
    --  * set value to `-1` to force check setting with lower priority
    --  * set value to `0` to unlimited, and stop checking settings with lower priority.
    msg_size    bigint                  NOT NULL DEFAULT -1, -- Limit of single (received) message size, in bytes.
    max_msgs    bigint                  NOT NULL DEFAULT -1, -- Number of max (received) messages in total.
    max_quota   bigint                  NOT NULL DEFAULT -1 -- Number of current (received) messages.
);

CREATE INDEX idx_account ON throttle (account);

-- Track per-user throttle.
CREATE TABLE throttle_tracking (
    id SERIAL PRIMARY KEY,
    -- foreign key of `throttle.id`
    tid         BIGINT                  REFERENCES throttle(id),
    -- tracking account. e.g. user@domain, @domain, '@.'.
    account     VARCHAR(255)            NOT NULL DEFAULT '',    -- Sender or recipient

    -- Track accumulated msgs/quota since init tracking.
    cur_msgs    BIGINT   NOT NULL DEFAULT 0, -- Number of current messages.
    cur_quota   BIGINT        NOT NULL DEFAULT 0, -- Current accumulated message size in total, in bytes.

    -- Track initial and last tracking time
    init_time   BIGINT NOT NULL DEFAULT 0, -- The time we initial the throttling.
    last_time   BIGINT NOT NULL DEFAULT 0 -- The time we last track the throttling.
);

CREATE INDEX idx_tid_account ON throttle_tracking (tid, account);
