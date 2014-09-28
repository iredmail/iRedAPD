* Plugins for Amavisd integration:

    * White/Blacklisting, server-wide, per-domain, per-user.
      Note: with Amavisd policy lookup (@lookup_sql_dsn), we can store wblist
      in SQL table `amavisd.wblist`, whitelisted/blacklisted senders will be
      stored in `amavisd.mailaddr`.

    * [DONE] `plugins/amavisd_reject_message_size_limit.py`:
      ~~ Message size limit, server-wide, per-domain, per-user.
      Note: with Amavisd policy lookup (@lookup_sql_dsn), we can store message
      size limit in SQL table `amavisd.policy`. ~~

* Plugins for replacing Policyd/Cluebringer

    * [?] HELO restrictions.
        * [?] PCRE compatible regular expression support?
        * [?] Widecard (*, %, ?) support?

    * [?] Greylisting, server-wide, per-domain and per-user.
    * [?] Throttling

* Query required SQL columns instead of all
