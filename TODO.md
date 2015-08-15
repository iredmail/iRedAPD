* Hard-code plugin priority somewhere, then apply enabled plugins in particular
  order. This way we don't need to care about the order defined by user in
  `plugins =`.

* Replace `plugins/amavisd_message_size_limit.py` by `plugins/throttling.py`.

    * `tools/upgrade_iredapd.py`: remove this plugin in `settings.py`.

* plugins/greylisting.py:

    * server-wide, per-domain and per-user.

* [?] HELO restrictions.

    * [?] PCRE compatible regular expression support?
    * [?] Widecard (*, %, ?) support?
