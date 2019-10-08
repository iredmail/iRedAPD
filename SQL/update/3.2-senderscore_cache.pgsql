CREATE TABLE senderscore_cache (
    id              SERIAL PRIMARY KEY,
    client_address  VARCHAR(40) NOT NULL DEFAULT '',
    -- sender score: 1-100.
    score           INT DEFAULT 0,
    -- creation time
    time            BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX idx_senderscore_cache_client_address ON senderscore_cache (client_address);
CREATE INDEX idx_senderscore_cache_score ON senderscore_cache (score);
CREATE INDEX idx_senderscore_cache_time ON senderscore_cache (time);
