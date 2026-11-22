# odditytrend.com

WordPress content site (weird news and strange facts). Unrelated to the Mumtaz and C2P products.

| | |
|---|---|
| **Status** | Unknown whether deployed |
| **Code** | [`wordpress-sites/odditytrend-theme/`](../../wordpress-sites/odditytrend-theme/) — custom theme |
| **Installer** | [`wordpress-sites/deploy/setup-lemp.sh`](../../wordpress-sites/deploy/setup-lemp.sh) — nginx, MariaDB, PHP-FPM, WordPress, certificates |
| **Database** | Its own MariaDB database, one per site |

**Not moved.** Open PR #134 edits `wordpress-sites/`. Recommended home: its own repository and separate hosting from the client ERPs.

## Open points

- The installer leaves the WordPress setup page unclaimed and public; the first visitor becomes admin (audit APP-04).
