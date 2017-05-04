# Test iRedAPD

## Requirements

* Python modules:
    * pytest

## Preparations

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
