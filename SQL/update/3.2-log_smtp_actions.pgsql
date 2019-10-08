CREATE TABLE log_smtp_actions (
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

CREATE INDEX idx_log_smtp_actions_time ON log_smtp_actions (time);
CREATE INDEX idx_log_smtp_actions_time_num ON log_smtp_actions (time_num);
CREATE INDEX idx_log_smtp_actions_action ON log_smtp_actions (action);
CREATE INDEX idx_log_smtp_actions_reason ON log_smtp_actions (reason);
CREATE INDEX idx_log_smtp_actions_instance ON log_smtp_actions (instance);
CREATE INDEX idx_log_smtp_actions_client_address ON log_smtp_actions (client_address);
CREATE INDEX idx_log_smtp_actions_client_name ON log_smtp_actions (client_name);
CREATE INDEX idx_log_smtp_actions_reverse_client_name ON log_smtp_actions (reverse_client_name);
CREATE INDEX idx_log_smtp_actions_helo_name ON log_smtp_actions (helo_name);
CREATE INDEX idx_log_smtp_actions_sender ON log_smtp_actions (sender);
CREATE INDEX idx_log_smtp_actions_sender_domain ON log_smtp_actions (sender_domain);
CREATE INDEX idx_log_smtp_actions_sasl_username ON log_smtp_actions (sasl_username);
CREATE INDEX idx_log_smtp_actions_sasl_domain ON log_smtp_actions (sasl_domain);
CREATE INDEX idx_log_smtp_actions_recipient ON log_smtp_actions (recipient);
CREATE INDEX idx_log_smtp_actions_recipient_domain ON log_smtp_actions (recipient_domain);
CREATE INDEX idx_log_smtp_actions_encryption_protocol ON log_smtp_actions (encryption_protocol);
CREATE INDEX idx_log_smtp_actions_encryption_cipher ON log_smtp_actions (encryption_cipher);
CREATE INDEX idx_log_smtp_actions_server_address ON log_smtp_actions (server_address);
CREATE INDEX idx_log_smtp_actions_server_port ON log_smtp_actions (server_port);
