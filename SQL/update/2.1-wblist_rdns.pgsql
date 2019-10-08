CREATE TABLE wblist_rdns (
    id      SERIAL PRIMARY KEY,
    rdns    VARCHAR(255) NOT NULL DEFAULT '',   -- reverse DNS name of sender IP address
    wb      VARCHAR(10) NOT NULL DEFAULT 'B'    -- W=whitelist, B=blacklist
);
CREATE UNIQUE INDEX idx_wblist_rdns_rdns ON wblist_rdns (rdns);
CREATE INDEX idx_wblist_rdns_wb ON wblist_rdns (wb);

-- Blacklists
INSERT INTO wblist_rdns (rdns, wb) VALUES ('.dynamic.163data.com.cn', 'B');
INSERT INTO wblist_rdns (rdns, wb) VALUES ('.cable.dyn.cableonline.com.mx', 'B');
INSERT INTO wblist_rdns (rdns, wb) VALUES ('.dyn.user.ono.com', 'B');
INSERT INTO wblist_rdns (rdns, wb) VALUES ('.static.skysever.com.br', 'B');
INSERT INTO wblist_rdns (rdns, wb) VALUES ('.castelecom.com.br', 'B');
INSERT INTO wblist_rdns (rdns, wb) VALUES ('.clients.your-server.de', 'B');
