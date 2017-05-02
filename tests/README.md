# Test iRedAPD

## Requirements

* pytest

## Preparations

* Add settings below in `/opt/iredapd/settings.py` BEFORE running tests:

```
ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = True
```

Restarting iRedAPD service is required.

* Create file `/opt/iredapd/tests/tsettings.py`, add password for SQL user
  `vmailadmin`:

```
vmail_db_password = 'xxxx'
```

## Run tests

```
cd /opt/iredapd/tests
bash main.sh
```
