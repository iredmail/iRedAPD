* Query required SQL columns instead of all
* Plugins:
    + ~~ Message size limit, server-wide, per-domain, per-user.
      Note: with Amavisd policy lookup (@lookup_sql_dsn), we can store message
      size limit in SQL table `amavisd.policy`. ~~

    + White/Blacklisting, server-wide, per-domain, per-user.
      Note: with Amavisd policy lookup (@lookup_sql_dsn), we can store wblist
      in SQL table `amavisd.wblist`, whitelisted/blacklisted senders will be
      stored in `amavisd.mailaddr`.

    ? HELO restrictions.
        ? PCRE compatible regular expression support?
        ? Widecard (*, %, ?) support?

    + Greylisting, server-wide, per-domain and per-user.
    ? Throttling support
