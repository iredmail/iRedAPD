CREATE TABLE srs_exclude_domains (
    id      SERIAL PRIMARY KEY,
    domain  VARCHAR(255) NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX idx_srs_exclude_domains_domain ON srs_exclude_domains (domain);
