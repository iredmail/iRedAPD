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
