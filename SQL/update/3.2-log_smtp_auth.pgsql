CREATE TABLE log_smtp_auth (
    id      SERIAL PRIMARY KEY,
    time    TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    time_num    BIGINT NOT NULL DEFAULT 0,
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
CREATE INDEX idx_log_smtp_auth_time ON log_smtp_auth (time);
CREATE INDEX idx_log_smtp_auth_time_num ON log_smtp_auth (time_num);
CREATE INDEX idx_log_smtp_auth_instance ON log_smtp_auth (instance);
CREATE INDEX idx_log_smtp_auth_client_address ON log_smtp_auth (client_address);
CREATE INDEX idx_log_smtp_auth_client_name ON log_smtp_auth (client_name);
CREATE INDEX idx_log_smtp_auth_reverse_client_name ON log_smtp_auth (reverse_client_name);
CREATE INDEX idx_log_smtp_auth_helo_name ON log_smtp_auth (helo_name);
CREATE INDEX idx_log_smtp_auth_sender ON log_smtp_auth (sender);
CREATE INDEX idx_log_smtp_auth_sender_domain ON log_smtp_auth (sender_domain);
CREATE INDEX idx_log_smtp_auth_sasl_username ON log_smtp_auth (sasl_username);
CREATE INDEX idx_log_smtp_auth_sasl_domain ON log_smtp_auth (sasl_domain);
CREATE INDEX idx_log_smtp_auth_recipient ON log_smtp_auth (recipient);
CREATE INDEX idx_log_smtp_auth_recipient_domain ON log_smtp_auth (recipient_domain);
CREATE INDEX idx_log_smtp_auth_encryption_protocol ON log_smtp_auth (encryption_protocol);
CREATE INDEX idx_log_smtp_auth_encryption_cipher ON log_smtp_auth (encryption_cipher);
CREATE INDEX idx_log_smtp_auth_server_address ON log_smtp_auth (server_address);
CREATE INDEX idx_log_smtp_auth_server_port ON log_smtp_auth (server_port);
