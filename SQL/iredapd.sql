-- Track all in/out sessions.
CREATE TABLE IF NOT EXISTS session_tracking (
    id BIGINT(20) UNSIGNED AUTO_INCREMENT,
    -- the current time in seconds since the Epoch
    time BIGINT NOT NULL,
    queue_id VARCHAR(255) NOT NULL DEFAULT '',
    client_address VARCHAR(255) NOT NULL DEFAULT '',
    client_name VARCHAR(255) NOT NULL DEFAULT '',
    reverse_client_name VARCHAR(255) NOT NULL DEFAULT '',
    helo_name VARCHAR(255) NOT NULL DEFAULT '',
    sender VARCHAR(255) NOT NULL DEFAULT '',
    recipient VARCHAR(255) NOT NULL DEFAULT '',
    recipient_count INT(10) UNSIGNED DEFAULT 0,
    instance VARCHAR(255) NOT NULL DEFAULT '',
    sasl_username VARCHAR(255) NOT NULL DEFAULT '',
    size BIGINT(20) UNSIGNED DEFAULT 0,
    encryption_protocol VARCHAR(255) NOT NULL DEFAULT '',
    encryption_cipher VARCHAR(255) NOT NULL DEFAULT '',
    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE INDEX session_tracking_time          ON session_tracking (time);
CREATE INDEX session_tracking_sender        ON session_tracking (sender);
CREATE INDEX session_tracking_recipient     ON session_tracking (recipient);
CREATE INDEX session_tracking_sasl_username ON session_tracking (sasl_username);
CREATE INDEX session_tracking_instance      ON session_tracking (instance);
CREATE INDEX session_tracking_idx1          ON session_tracking (queue_id, client_address, sender);

-- Throttling
--
-- Possible value for throttle setting: msg_size, max_msgs, max_quota.
--
--  - -1: inherit from setting with lower priority
--  - 0:  no limit.
--  - XX (an integer number): explicit limit. e.g. max_msgs=100 -> up to 100 messages.
--
-- Sender throttling
CREATE TABLE throttle_sender (
    id          BIGINT(20) UNSIGNED AUTO_INCREMENT,
    user        VARCHAR(255)            NOT NULL DEFAULT '', -- Sender

    -- Throttle settings
    priority    TINYINT(1) UNSIGNED     NOT NULL DEFAULT 0,
    period      INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Peroid, in seconds.
    msg_size    INT(10)                 NOT NULL DEFAULT -1, -- Limit of single message size, in bytes.
    max_msgs    MEDIUMINT(8)            NOT NULL DEFAULT -1, -- Number of max messages in total.
    max_quota   INT(10)                 NOT NULL DEFAULT -1, -- Max accumulated message size in total, in bytes.

    -- Track accumulated msgs/quota since init tracking.
    cur_msgs    MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of current messages.
    cur_quota   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Current accumulated message size in total, in bytes.

    -- Track accumulated msgs/quota
    total_msgs  MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of sent message in total.
    total_quota BIGINT(20) UNSIGNED     NOT NULL DEFAULT 0, -- Number of sent message in total.

    -- Initial and last tracking time
    init_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we initial the throttling.
    last_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we last track the throttling.

    local       VARCHAR(1)              NOT NULL DEFAULT 'N', -- Sender is a local account: Y (local), N (external).

    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE UNIQUE INDEX user ON throttle_sender (user);

-- Recipient throttling
CREATE TABLE throttle_rcpt (
    id          BIGINT(20) UNSIGNED AUTO_INCREMENT,
    user        VARCHAR(255)            NOT NULL DEFAULT '', -- Recipient

    msg_size    INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Limit of single (received) message size, in bytes.

    max_msgs    MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of max (received) messages in total.
    cur_msgs    MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of current (received) messages.

    max_quota   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Max accumulated (received) message size in total, in bytes.
    cur_quota   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Current accumulated (received) message size in total, in bytes.

    period      INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Peroid, in seconds.
    init_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we initial the throttling.
    last_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we last track the throttling.
    priority    TINYINT(1) UNSIGNED     NOT NULL DEFAULT 0,

    total_msgs  MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of received message in total.
    total_quota BIGINT(20) UNSIGNED     NOT NULL DEFAULT 0, -- Number of received message in total.
    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE UNIQUE INDEX user ON throttle_rcpt (user);
