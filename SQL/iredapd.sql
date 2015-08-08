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
    PRIMARY KEY (id),
    INDEX (time),
    INDEX (sender),
    INDEX (recipient),
    INDEX (sasl_username),
    INDEX (instance)
) ENGINE=InnoDB;

CREATE INDEX session_tracking_idx1 ON session_tracking (queue_id, client_address, sender);
