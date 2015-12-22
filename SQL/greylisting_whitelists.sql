-- Don't apply greylist on big ISPs or web sites, it's useless because they
-- always retry.
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '216.239.32.0/19', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '64.233.160.0/19', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '66.249.80.0/20', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '72.14.192.0/18', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '209.85.128.0/17', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '66.102.0.0/20', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '74.125.0.0/16', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '64.18.0.0/20', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '207.126.144.0/20', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '173.194.0.0/16', 'Google');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.54.190.0/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.54.190.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.54.190.128/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.54.190.192/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.116.0/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.111.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.116.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.111.128/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.34.0/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.34.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.34.128/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.34.192/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.90.0/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.90.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.90.128/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.55.90.192/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.54.51.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '65.54.61.64/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '207.46.66.0/28', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '157.55.0.192/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '157.55.1.128/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '157.55.2.0/26', 'Microsoft');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '157.55.2.64/26', 'Microsoft');

INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '69.63.179.25', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '69.63.178.128/25', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '69.63.184.0/25', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '66.220.144.128/25', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '66.220.155.0/24', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '69.171.232.128/25', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '66.220.157.0/25', 'Facebook');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '69.171.244.0/24', 'Facebook');

INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '199.16.156.0/22', 'Twitter');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '199.59.148.0/22', 'Twitter');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '8.25.194.26/31', 'Twitter');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '204.92.114.203', 'Twitter');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '204.92.114.204/31', 'Twitter');

INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '199.101.162.0/25', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '108.174.3.0/24', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '108.174.6.0/24', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '2620:109:c00d:104::/64', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '2620:109:c006:104::/64', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '2620:109:c003:104::/64', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '216.136.162.65', 'LinkedIn');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '199.101.161.130', 'LinkedIn');

-- Amazone SES.
-- Get by query DNS: dig TXT amazonses.com +short| grep 'v=spf1'
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '199.255.192.0/22', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '199.127.232.0/22', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '54.240.0.0/18', 'Amazon');
-- Amazon
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '52.95.49.88/29', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '52.95.48.152/29', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '72.21.217.142/32', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '205.251.233.36/32', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '205.251.233.32/32', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '106.50.16.0/28', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '176.32.127.0/24', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '176.32.105.0/24', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '178.236.10.128/26', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '72.21.212.0/25', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '203.81.17.0/24', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '212.123.28.40/32', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '194.7.41.152/28', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '194.154.193.192/27', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '72.21.192.0/19', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '87.238.80.0/21', 'Amazon');
INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '207.171.160.0/19', 'Amazon');

-- INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '168.100.1.3', 'postfix.org');
-- INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '168.100.1.4', 'postfix.org');
-- INSERT INTO greylisting_whitelists (account, sender, comment) VALUES ('@.', '168.100.1.7', 'postfix.org');

-- TODO: Instgram
