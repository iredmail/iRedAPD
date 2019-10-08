CREATE TABLE greylisting_whitelist_domain_spf (
    id      SERIAL PRIMARY KEY,
    account VARCHAR(255)    NOT NULL DEFAULT '',
    sender  VARCHAR(255)    NOT NULL DEFAULT '',
    comment VARCHAR(255) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_greylisting_whitelist_domain_spf_account_sender ON greylisting_whitelist_domain_spf (account, sender);
CREATE INDEX idx_greylisting_whitelist_domain_spf_comment ON greylisting_whitelist_domain_spf (comment);
