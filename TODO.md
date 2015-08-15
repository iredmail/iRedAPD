* Replace `plugins/amavisd_message_size_limit.py` by `plugins/throttling.py`.

    * `tools/upgrade_iredapd.py`: remove this plugin in `settings.py`.

* Cron job to clean up `throttle` sql table (remove non-existing user?).
* plugins/greylisting.py:

    * server-wide, per-domain and per-user.

* [?] HELO restrictions.

    * [?] PCRE compatible regular expression support?
    * [?] Widecard (*, %, ?) support?
