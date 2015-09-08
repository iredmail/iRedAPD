* `plugins/throttling.py`: able to throttle all users together with per-domain
  or global setting, not just per-user.

* Cron job to clean up `throttle` sql table (remove non-existing user?).
* plugins/greylisting.py:

    * server-wide, per-domain and per-user.

* [?] HELO restrictions.

    * [?] PCRE compatible regular expression support?
    * [?] Widecard (*, %, ?) support?
