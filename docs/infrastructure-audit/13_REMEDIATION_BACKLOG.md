# 13 — Remediation Backlog

**Status of every item: Not started.** Nothing is to be executed without the approval named, recorded in `15_DECISIONS_AND_APPROVALS.md`. Items are grouped by type; the order of execution is in `14_IMPLEMENTATION_ROADMAP.md`.

Columns: **Sev** = severity of the risk addressed · **Chg** = does it change production? (No / Config / Restart / Data) · **Effort** S ≤ 2 h, M ≤ 1 day, L > 1 day.

## V — Verification pack (read-only; run by the owner on the VPS)

| ID | What it establishes | Closes the unknown in |
|---|---|---|
| V-01 | Host: OS, CPU/RAM, disk, uptime, pending reboots | 01 |
| V-02 | Listening sockets with owning process; `ufw` rules; provider firewall (hPanel) | F-01 |
| V-03 | nginx: every `server_name` → root / upstream, from `nginx -T` | F-07, F-12 |
| V-04 | Every Odoo/FastAPI/pm2/Docker unit: `ExecStart`, user, config path; configs with passwords masked | 01, 06 |
| V-05 | Each checkout under `/opt`: remote, branch, commit, dirty/untracked files | F-04, F-05 |
| V-06 | What listens on 3000, 8001, 8002, 8003, 8080, 8800; pm2 list; `docker ps` | F-11, F-24 |
| V-07 | Requests per vhost over the last 30 days (counts only) | 13 §unused resources |
| V-08 | Database metadata (`05` §6, V-DB-1 … 8) | F-06, F-13 |
| V-09 | Crons, timers, existing dump files, Hostinger snapshots | F-02 |
| V-10 | `certbot certificates`; registrar expiry and auto-renew for each domain | F-10, F-18 |
| V-11 | Per Odoo DB: installed modules, active crons, server-action count, presence of specific config keys (names only); whether administrator passwords were changed from defaults (owner's statement — **not tested by guessing**) | F-01, F-23, 06 |
| V-12 | Agency OS: which auth flags are set (names only), basic auth present?, run-as user, permissions on `.env` and stores, `cryptography`/WeasyPrint installed? | F-28 |

### Script for V-01 … V-10 and V-12

Read-only. It writes nothing except its own output to the terminal. Review it before running; run as root; paste the output back **privately** (not into the public repository).

```bash
#!/usr/bin/env bash
# Read-only inventory. Masks passwords/secrets. Writes nothing.
mask() { sed -E 's/((passw(or)?d|passwd|secret|token|api[_-]?key|_key|_pass)[A-Za-z_]*[[:space:]]*[=:][[:space:]]*).*/\1***masked***/I'; }
h() { printf '\n===== %s =====\n' "$*"; }

h V-01 host;        hostnamectl 2>/dev/null | grep -Ev 'Machine ID|Boot ID'; nproc; free -h; df -hT / /var /opt 2>/dev/null; uptime
                    [ -f /var/run/reboot-required ] && echo "REBOOT REQUIRED"
h V-02 sockets;     ss -ltnpH | awk '{print $4, $6}' | sort -u
h V-02 ufw;         ufw status verbose 2>/dev/null
h V-03 nginx map;   nginx -T 2>/dev/null | grep -E '^\s*(server_name|listen|root|proxy_pass|auth_basic|allow|deny|ssl_certificate )|^# configuration file' | mask
h V-04 units;       systemctl list-units --type=service --all --no-legend 2>/dev/null | grep -Ei 'odoo|faizy|delivery|zaki|erp|pm2|uvicorn|nginx|postgres|maria|mysql|docker|php' 
                    for u in $(systemctl list-unit-files --no-legend | awk '{print $1}' | grep -Ei 'odoo|faizy|delivery|zaki|erp-server|mumtaz'); do
                      echo "--- $u"; systemctl cat "$u" 2>/dev/null | grep -E '^(ExecStart|User|Group|WorkingDirectory|EnvironmentFile|Environment)=' | mask; done
h V-04 odoo confs;  for f in /etc/odoo/*.conf /etc/odoo*.conf /opt/faizy/odoo.conf; do [ -f "$f" ] && { echo "--- $f ($(stat -c '%U:%G %a' "$f"))"; grep -vE '^\s*(;|#|$)' "$f" | mask; }; done
h V-05 checkouts;   for d in /opt/*/ /opt/*/*/; do [ -d "$d/.git" ] && { echo "--- $d"; git -C "$d" remote get-url origin 2>/dev/null | sed -E 's#//[^@/]+@#//***@#'; git -C "$d" rev-parse --abbrev-ref HEAD; git -C "$d" log -1 --format='%h %cs %s'; git -C "$d" status --porcelain | head -20; }; done
h V-06 runtimes;    command -v pm2 >/dev/null && pm2 ls 2>/dev/null; command -v docker >/dev/null && docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
h V-07 traffic;     for f in /var/log/nginx/*access*.log; do [ -f "$f" ] && printf '%8d  %s\n' "$(wc -l < "$f")" "$f"; done
h V-08 databases;   sudo -u postgres psql -Atc "select d.datname, r.rolname, pg_size_pretty(pg_database_size(d.datname)), d.datallowconn from pg_database d join pg_roles r on r.oid=d.datdba where not d.datistemplate order by pg_database_size(d.datname) desc"
                    sudo -u postgres psql -Atc "select rolname, rolsuper, rolcreatedb, rolcanlogin from pg_roles where rolname !~ '^pg_'"
                    sudo -u postgres psql -Atc "select datname, usename, application_name, count(*) from pg_stat_activity where datname is not null group by 1,2,3 order by 1"
                    sudo -u postgres psql -Atc "show listen_addresses"
h V-09 schedules;   crontab -l 2>/dev/null; for u in odoo faizy postgres www-data; do echo "--- $u"; crontab -l -u "$u" 2>/dev/null; done; ls /etc/cron.d/ 2>/dev/null
                    systemctl list-timers --all --no-legend 2>/dev/null | awk '{print $NF, $(NF-1)}'
                    find / -xdev \( -name '*.dump' -o -name '*.sql.gz' -o -name '*.backup' \) -mtime -45 -printf '%TY-%Tm-%Td %10s %p\n' 2>/dev/null | sort | tail -40
h V-10 certs;       certbot certificates 2>/dev/null | grep -E 'Certificate Name|Domains|Expiry'
h V-12 agency-os;   E=/opt/mumtaz/c2p-delivery-system/delivery_api/.env; [ -f "$E" ] && { stat -c '%U:%G %a %n' "$E"; grep -oE '^(C2P_ADMIN_AUTH|MULTITENANT|C2P_SECRET_KEY|C2P_JWT_SECRET|C2P_ALLOW_PLAINTEXT_SECRETS|C2P_CORS|C2P_LLM_PROVIDER)=' "$E" | sed 's/=$/ = (set)/'; grep -E '^(C2P_ADMIN_AUTH|MULTITENANT|C2P_ALLOW_PLAINTEXT_SECRETS)=' "$E"; }
                    stat -c '%U:%G %a %n' /opt/mumtaz/c2p-delivery-system/delivery_api/*.db 2>/dev/null
```

The three flag values printed in V-12 are booleans, not secrets. V-11 uses the SQL in `06` §4.

## S — Security

| ID | Action | Sev | Chg | Effort | Depends on | Backup first | Validation | Rollback | Approval |
|---|---|---|---|---|---|---|---|---|---|
| S-01 | Make the GitHub repository private (add a read credential to each server checkout first) | Critical | No | S | — | — | Anonymous clone fails; `git ls-remote` works on each checkout | Re-publish | Owner |
| S-02 | Replace any default-strength Odoo administrator **login** password on every instance; store in the vault | Critical | Data (one user record) | S | V-11 | — | Old password refused; new one in vault | Vault holds the value | Owner |
| S-03 | IG2: nginx vhost + certificate on its hostname → announce URL to users → `http_interface = 127.0.0.1` on `odoo3` → remove firewall rule for 8071 | Critical | Config + Restart | M | V-02, V-03; D-07 | B-02 | HTTPS login works; `IP:8071` refused from outside | Restore conf line; re-add rule | Owner + client |
| S-04 | Same for every other application port found open in V-02 (8069, 8070, 8075, 8080 …) | Critical | Config + Restart | M | V-02 | B-02 | `ss` shows `127.0.0.1` binds only | Per instance | Owner |
| S-05 | Default-deny inbound at the provider firewall: allow 22 (restricted), 80, 443 | High | Config | S | S-03, S-04 | — | External check | Remove rule set | Owner |
| S-06 | Add `db_name = <its own database>` to `odoo2` and `odoo3` | High | Config + Restart | S | V-04 | B-02 | `pg_stat_activity`: each process only on its own database | Remove the line | Owner |
| S-07 | Resolve the two servers on `Mumtaz_C2P`: identify which vhosts hit :8069; move them; stop the redundant unit (do not delete) | High | Config + Restart | M | V-03, V-04 | B-02 | One application name per database; `erp.` opens the intended DB | Start the unit again | Owner |
| S-08 | Agency OS: confirm an auth mode is active and `C2P_SECRET_KEY` is set; if open, enable admin login | High | Config + Restart | S | V-12 | Copy `.env` + stores | `/engagements` returns 401 without a token | Restore `.env` | Owner |
| S-09 | `location ~ ^/web/database { deny all; }` on every Odoo vhost; confirm `list_db = False` | High | Config (reload) | S | V-03 | `/etc/nginx` tarball | `/web/database/manager` → 403 | Remove lines | Tech lead |
| S-10 | nginx `limit_req` on `/web/login`, `/auth/*`, anonymous form endpoints | Medium | Config (reload) | S | V-03 | tarball | 429 after burst | Remove lines | Tech lead |
| S-11 | Make sure nothing listens publicly on 3000/8001/8002/8003; stop units for services with no maintained source | High | Restart (stop) | S | V-06, D-08 | — | Ports closed | Start unit | Owner |
| S-12 | Secrets inventory; unique DB password per instance; rotate anything copied between configs or ever committed; `.env.example` placeholders | Medium | Config + Restart | L | R-13 | B-02 | Each service starts with its own secret | Previous values in vault for 7 days | Owner |

## B — Backup and recovery

| ID | Action | Sev | Chg | Effort | Validation | Approval |
|---|---|---|---|---|---|---|
| B-01 | Check disk headroom against database + filestore sizes before any dump | Critical | No | S | Free space > 2× largest database | — |
| B-02 | One-off manual backup, off-peak: `pg_dump -Fc` per production database, `pg_dumpall --globals-only`, each filestore, SQLite stores via `.backup`, config bundle; copy **off the host** | Critical | No (read load) | M | Files exist off-host; checksums recorded | Owner |
| B-03 | Restore one production dump on an isolated machine, neutralised; record counts | Critical | No | M | Odoo starts; module list and a few row counts match | Owner |
| B-04 | Nightly timer: per-database dump + matching filestore as role `backup_ro` | Critical | Config | M | Timer ran; files dated today | Owner |
| B-05 | Encrypt with a key not stored on the VPS; upload to versioned object storage in another provider; 7/4/6 retention | Critical | Config | M | Object listed; decrypts with the offline key | Owner (D-05) |
| B-06 | Written restore-drill procedure including `odoo neutralize`; monthly drill on the staging host; results logged | High | No | M | Drill log entry | Tech lead |
| B-07 | Heartbeat: job pings the monitor on success; alert after 26 h of silence | High | Config | S | Test alert received | Tech lead |

## O — Operations

| ID | Action | Sev | Chg | Effort | Approval |
|---|---|---|---|---|---|
| O-01 | Fix `erp.` live-update upstream (currently the Jewel container's port) and the dead `ig2.` websocket upstream | High | Config (reload) | S | Tech lead |
| O-02 | Disable the crash-looping `erp-server` unit (stop + disable, keep files) | Medium | Restart (stop) | S | Owner |
| O-03 | Export the 25 CRM server actions into a versioned module; replace DB copies via module upgrade on a staging copy first | High | Data | L | Owner |
| O-04 | Run `collect_production_addons.sh` (already written, read-only for Odoo) and commit every server-only module | High | No | M | Tech lead |
| O-05 | Monitoring per `11` §7: uptime, wrong-database check, certificates, domain, disk, backup heartbeat | Medium | Config | M | Tech lead |
| O-06 | Release tags; per-product deploy script on the `stage.sh` pattern; per-product `DEPLOY_LOG.md` | Medium | Config | L | Tech lead |
| O-07 | GitHub Environments with required reviewers per product; forced-command deploy keys; pin actions by SHA; remove input interpolation into shell; `permissions:` blocks | Medium | No | M | Tech lead |
| O-08 | Staging-first rule in deploy scripts; staging restores always neutralised | Medium | No | M | Tech lead |
| O-09 | Path-filtered CI per product; delivery-API tests and platform fresh-install test (PR #172) as required checks | Medium | No | M | Tech lead |
| O-10 | `apt-mark hold odoo`; documented, rehearsed upgrade procedure | Medium | Config | S | Owner |

## A — Application fixes

| ID | Action | Addresses | Sev | Effort |
|---|---|---|---|---|
| A-01 | Review and merge the e-invoice CSRF fix stranded on `security/h1-h2-…` (needs a staging test) | ODOO-25 | Low | S |
| A-02 | Triage the 12 open PRs; in particular PR #126 (ZAKI auth hardening) and PR #134 (server hardening script) | F-40 | Low | M |
| A-03 | Agency OS: refuse to start without an auth mode; accept only `1`; startup log line stating the mode | C2P-01 | High | S |
| A-04 | Agency OS: drop stored key/token on any URL/repo change; never use a stored secret against a request-supplied URL; scrub git errors; token via `GIT_ASKPASS`; remove default Odoo credentials; add `cryptography` to requirements; fail loudly on decrypt errors | C2P-02, -03, -12, -13 | High | M |
| A-05 | Agency OS: validate `subdir`; validate branding (hex colours, `data:image/*` logos) and escape on output; restricted WeasyPrint fetcher; block private ranges on user-supplied URLs | C2P-04, -05, -09 | High | M |
| A-06 | Console: escape quotes in `esc()`; coerce numeric fields; SRI on CDN scripts; CSP; move token to an httpOnly cookie | C2P-08 | Medium | M |
| A-07 | Agency OS: login rate limit and shorter token life; atomic approval state change; field allow-list for config writes; refuse empty-domain writes; untrusted-content guardrails in prompts; no auto-send of replies | C2P-10, -11 | Medium | L |
| A-08 | Agency OS: run its tests in CI; before ever enabling multi-tenant mode fix client cache keying, env fallbacks, edition and status enforcement | C2P-06, -07, -18 | High (if multi-tenant) | L |
| A-09 | SSO: per-tenant or asymmetric secret, host binding, nonce, TTL cap; until then do not install `mumtaz_sso` on shared servers | ODOO-01, -11 | Critical | M |
| A-10 | Faizy: record rule on `faizy.document`; restrict worker writes on orders to action methods; verification + throttle on public signup | ODOO-06, -16, -17 | High | M |
| A-11 | Platform: make the group-rewrite and Stripe methods private and group-checked; remove `sudo()` from `/zaki/api/snapshot`, `/app*`, portal routing; add company domains; fix marketplace write rule | ODOO-02, -03, -04, -05, -08 | High | M |
| A-12 | Platform remainder: throttle anonymous endpoints; Stripe webhook retries and amount checks; e-invoice status logic + tests; record rules for company-scoped models; vendor portal approval flow; SSRF guards; provisioning wizard flags; Odoo 19 API drift; missing dependencies; self-hosted fonts | ODOO-09 … -35 | Medium | L |
| A-13 | IG2: install the accounting-kit hardening already written for Pharma, on a staging copy first; record the third-party module's pinned commit | F-15 | High | S–M |
| A-14 | ZAKI / portal / marketplace: after D-08 either retire all (archive code, stop services, park hostnames) or rebuild **one** ZAKI with real JWT verification, tenant from token, non-superuser DB role, per-tenant Odoo credentials, server-side provider keys | APP-01, -02, -05 … -10, -14 … -21 | Critical/High | S (retire) / L (rebuild) |
| A-15 | Pin dependencies with lockfiles (Python and Node); upgrade the browser PDF library after checking the one function used; enable `npm audit` for the Jewel front end | F-36 | Medium | M |
| A-16 | Jewel: explicit opt-in before attaching fit measurements; correct the on-screen privacy copy; do not pass fit data to the voice vendor without consent; remove or test-gate the one-time-code echo; never install the demo module on a reachable database | APP-22, -23, ODOO-07 | Medium | M |
| A-17 | Installers: WordPress — run `wp core install` non-interactively, verify downloads, tighten permissions; Faizy — no public listener until the admin password is set; delete scripts with literal credentials | APP-03, -04, -11, -24 | High | M |

## Unused or duplicate resources — classification and retirement plan

Classes: 1 Confirmed active · 2 Likely active · 3 Unknown ownership · 4 Potentially unused · 5 Confirmed obsolete (subject to owner verification). **Nothing is to be deleted on the strength of this table.**

| Resource | Class | Evidence | Proposed path |
|---|---|---|---|
| `Mumtaz_C2P`, `Mumtaz_IG2`, `faizy_prod` | 1 | Recent owner-run output | Retain |
| `Mumtaz_ERP` + `odoo2` | 2 | Unit active 2026-11-18 | Retain; confirm users (V-07, V-08) |
| `odoo.service` :8069 | 3 | Pinned to the same DB as `odoo4` | S-07 |
| `mumtaz_pharma`, `jewel_demo` | 1 (staging) | Logs, CI | Retain; move to staging host |
| `mumtaz_platform` DB | 3 | Listed 2026-10-05; rebuild stalled since July | D-08 → archive |
| `mumtaz_erp` (lower case), `IG2`, `scratch_pre` | 4 | Listed once; one described as dead | V-DB-5 → dump → revoke connections 7 days → drop (R-16) |
| `Mumtaz_C2P_staging` | 4 | Owned by `postgres`; holds real leads | Same, **with priority** — it is unprotected personal data |
| `erp-server.service` | 5 | Crash loop; source deleted | O-02 |
| `zaki-server`, pm2 apps | 3 | Source deleted; state unknown | V-06 → S-11 |
| `ig2.mumtaz.digital` vhost | 4 | Websocket to a dead port; users use the raw port | Fix and adopt (S-03) rather than remove |
| `*.mumtaz.io` nginx template | 5 | One legacy file; no other reference | Archive |
| Duplicate checkout `/opt/custom_addons/Mumtaz` vs `/opt/mumtaz` | 3 | Both on a feature branch | V-05 → R-11 |
| `apps/zaki`, `apps/erp`, `apps/platform`, `apps/addons` | 5 | Depend on deleted code; untouched since May | R-08 |
| `apps/portal`, `apps/marketplace`, `apps/website`, `platform/marketing` | 4 | Backend deleted / superseded | V-03, V-07 → R-08 |
| `apps/zaki-ai`, `platform/zaki` | 3 | Two rival implementations | D-08 |
| Root Docker stack, `scripts/deploy-*.sh`, `ops/deployment/*` | 5 | Never ran; contradict the server | R-08 |
| 28 merged branches | 5 | Fully contained in `main` | R-17 |
| `tools/scrapers/` | 4 | Dormant since July | D-13 |
| WordPress sites | 3 | Deployed? unknown | V-03 → D-12 |
| Old dumps under `/var/local/pharma-staging/backups`, `/opt/mumtaz/backups` | 3 | Created 2026-11-18 | Keep until automated backups exist; then apply retention |
