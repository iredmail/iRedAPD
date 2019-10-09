CREATE TABLE senderscore_cache (
    client_address  VARCHAR(40) NOT NULL DEFAULT '',
    score           INT DEFAULT 0,  -- score: 1-100.
    time            BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (client_address)
);
CREATE INDEX idx_senderscore_cache_score ON senderscore_cache (score);
CREATE INDEX idx_senderscore_cache_time ON senderscore_cache (time);
