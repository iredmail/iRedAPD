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
-- ------------
-- Valid settings:
--
--  *) For sender throttling:
--
--      * max_msgs: max number of sent messages
--      * max_quota: max number of accumulated message size
--      * msg_size: max size of single message
--
--  *) For recipient throttling:
--
--      * rcpt_max_msgs: max number of received messages
--      * rcpt_max_quota: max number of accumulated message size
--      * rcpt_msg_size: max size of single message
--
-- Sample setting:
--
-- *) Allow user 'user@domain.com' to send in 6 minutes (period_sent=360):
--
--      * max 100 msgs (max_msg=100;)
--      * max 4096000000 bytes (max_quota=4096000000)
--      * max size of single message is 10240000 bytes (msg_size=10240000)
--
--  INSERT INTO throttle (user, settings, period_sent, priority)
--                VALUES ('user@domain.com',
--                        'max_msgs:100;max_quota:4096000000;msg_size:10240000;',
--                        360,
--                        10);
--
-- *) Allow user 'user@domain.com' to receive in 6 minutes (period=360):
--
--      * max 100 msgs (max_msg=100;)
--      * max 4096000000 bytes (max_quota=4096000000)
--      * max size of single message is 10240000 bytes (msg_size=10240000)
--
--  INSERT INTO throttle (user, settings, period_rcvd, priority)
--                VALUES ('user@domain.com',
--                        'rcpt_max_msgs:100;rcpt_max_quota:4096000000;rcpt_msg_size:10240000;',
--                        360,
--                        10);
--
-- *) Allow user 'user@domain.com' to send and receive in 6 minutes (period=360):
--
--      * send max 100 msgs (max_msg=100;)
--      * send max 4096000000 bytes (max_quota=4096000000)
--      * send max size of single message is 10240000 bytes (msg_size=10240000)
--      * receive max 100 msgs (max_msg=100;)
--      * receive max 4096000000 bytes (max_quota=4096000000)
--      * receive max size of single message is 10240000 bytes (msg_size=10240000)
--
--  INSERT INTO throttle (user, settings, period_sent, priority_sent, priority_rcvd, priority)
--                VALUES ('user@domain.com',
--                        'max_msgs:100;max_quota:4096000000;msg_size:10240000;rcpt_max_msgs:100;rcpt_max_quota:4096000000;rcpt_msg_size:10240000;',
--                        360,
--                        360,
--                        10);
-- ------------
-- Possible value for throttle setting: msg_size, max_msgs, max_quota.
--
--  * XX (an integer number): explicit limit. e.g. 100. (max_msgs=100 means up to 100 messages)
--  * -1: inherit from setting with lower priority
--  * 0:  no limit.
--
CREATE TABLE throttle (
    id          BIGINT(20) UNSIGNED AUTO_INCREMENT,
    user        VARCHAR(255)            NOT NULL DEFAULT '', -- Sender

    -- throttle settings.
    settings    TEXT,
    priority    TINYINT(1) UNSIGNED     NOT NULL DEFAULT 0,

    period   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Peroid, in seconds.
    rcpt_period   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Peroid, in seconds.

    -- Track accumulated msgs/quota since init tracking.
    cur_msgs    MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of current messages.
    cur_quota   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Current accumulated message size in total, in bytes.
    rcpt_cur_msgs    MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of current messages.
    rcpt_cur_quota   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- Current accumulated message size in total, in bytes.

    -- Track accumulated msgs/quota
    total_msgs  MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of sent message in total.
    total_quota BIGINT(20) UNSIGNED     NOT NULL DEFAULT 0, -- Number of sent message in total.
    rcpt_total_msgs  MEDIUMINT(8) UNSIGNED   NOT NULL DEFAULT 0, -- Number of sent message in total.
    rcpt_total_quota BIGINT(20) UNSIGNED     NOT NULL DEFAULT 0, -- Number of sent message in total.

    -- Track initial and last tracking time
    init_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we initial the throttling.
    last_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we last track the throttling.
    rcpt_init_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we initial the throttling.
    rcpt_last_time   INT(10) UNSIGNED        NOT NULL DEFAULT 0, -- The time we last track the throttling.

    is_local       VARCHAR(1)              NOT NULL DEFAULT 'N', -- Sender is a local account: Y (local), N (external).

    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE UNIQUE INDEX user ON throttle (user);
