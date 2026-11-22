# 09 — Backup, Disaster Recovery and Business Continuity

**Headline: there is no evidence that any production database, filestore or application store on this VPS has a working, restorable, off-site backup.** Under the audit's own rule ("never claim a backup is recoverable without verification"), every production system is classed **high operational risk** until a restore has been demonstrated.

## 1. Coverage matrix

| System | Database dump | Filestore / files | Frequency | Retention | Encrypted | Off-site | Last restore test | Verdict |
|---|---|---|---|---|---|---|---|---|
| C2P CRM (`Mumtaz_C2P`) | None automated. A manual procedure exists in `addons/c2p_project_tracker/scripts/backup_and_install.md`; an earlier audit notes it "was never carried out" | None | — | — | — | — | None | **Unprotected** |
| Platform ERP (`Mumtaz_ERP`) | None found | None | — | — | — | — | None | **Unprotected** |
| IG2 client (`Mumtaz_IG2`) | None found | None | — | — | — | — | None | **Unprotected** |
| Faizy (`faizy_prod`) | Not documented in the repository | Not documented | NV | NV | NV | NV | NV | **Unknown — treat as unprotected** |
| C2P Agency OS (SQLite + `.env` with the encryption key) | None found | None | — | — | — | — | None | **Unprotected.** Losing `C2P_SECRET_KEY` also makes the stored Odoo connection and GitHub token unrecoverable |
| zaki-server `users.db` | None found | — | — | — | — | — | None | Unprotected (if still in use) |
| Pharma staging | `stage.sh backup` + automatic pre-upgrade dumps (11 MB each, 2026-11-18) | Config tarball of `/etc/nginx`, `/etc/odoo*.conf`, unit files | On demand | Unbounded | No | **No — same disk** | Rollback path printed, not exercised | Adequate for staging |
| Jewel staging | `deploy/jewel-staging/backup.sh` — `pg_dump` + gzip, verifies non-empty | Not covered (Docker volume) | Nightly **if** the cron was installed (NV) | 14 days | No | **No — same disk** | `--restore` drill is scripted into a throwaway database; whether it was run is NV | Good design, unverified |
| Legacy Docker DB `mumtaz` | `scripts/backup.sh` from GitHub Action `backup.yml` | None | Nightly 02:00 UTC | 30 days | No | No | None | **Never ran** — see §2 |
| nginx / systemd / `/etc/odoo*.conf` | One tarball from 2026-11-18 (Pharma work) | — | Once | — | No | No | — | Incidental |
| TLS certificates and keys (`/etc/letsencrypt`) | None found | — | — | — | — | — | — | Re-issuable, but rate-limited |
| WordPress ×2 | None found | None | — | — | — | — | — | Unprotected (if deployed) |
| Git repository | GitHub is the only remote | — | — | — | — | — | — | Code is safe; **production code that is not in git is not** (F-05) |

## 2. Why the "nightly backup" does not exist

`backup.yml` is scheduled for 02:00 UTC daily. The GitHub API shows 920 runs of this workflow, every one a failure, each lasting zero seconds, triggered by `push` rather than `schedule`, and named by file path instead of by its `name:`. That is the signature of a workflow file GitHub refuses to parse. The cause is `if: ${{ secrets.SLACK_WEBHOOK != '' }}` — the `secrets` context is not allowed in `if:`. The same defect disables `deploy-production.yml`, `deploy-staging.yml` and `test.yml`. PR #168 fixes all four and has been open since 2026-11-19.

Even once the file parses, the job would still not protect production:

- It runs `scripts/backup.sh`, which dumps database `mumtaz` from the Docker Compose stack. Production does not run in that stack and has no database of that name.
- It dumps one database, no filestore, to `/opt/mumtaz/backups` on the same disk.
- Its Slack step reports "backup completed" unconditionally.

**Merging PR #168 will make the workflow start running against the VPS.** Decide what it should do before merging (see `15_DECISIONS_AND_APPROVALS.md`, D-06).

## 3. Recovery objectives

No RPO or RTO is defined anywhere. Proposed starting points for the owner to confirm:

| System | Proposed RPO | Proposed RTO | Rationale |
|---|---|---|---|
| IG2 client accounting | 24 h | 8 h | Third-party financial records; contractual exposure |
| C2P CRM | 24 h | 8 h | 41 users, daily BD activity |
| Faizy | 24 h | 8 h | Customer wallet and identity documents |
| Platform ERP | 24 h | 24 h | Tenant registry |
| C2P Agency OS | 24 h | 24 h | Engagement history is regenerable only in part |
| Staging tenants | 7 days | 72 h | Demo data, re-seedable |

## 4. Disaster scenarios today

| Scenario | Outcome with what exists today |
|---|---|
| VPS disk failure or provider-side loss | All production data lost. Code recoverable from GitHub **except** untracked modules and database-stored logic. Server layout must be rebuilt from memory |
| Accidental `dropdb` or bad module upgrade on `Mumtaz_IG2` | No restore point |
| Ransomware / host compromise | Same-disk dumps are lost with the host |
| Operator error in `/opt/mumtaz` (wrong branch checked out) | Several services change behaviour at once; rollback is `git checkout` by hand |
| Loss of `delivery_api/.env` | Encrypted connection and token records in SQLite become unreadable |
| Expired or lapsed domain | Ten subdomains go dark together; certbot renewals begin failing |
| Hostinger snapshot restore | **NV** whether VPS snapshots or weekly backups are enabled in hPanel — this is the single most valuable fact to check, because it may already provide a coarse safety net |

## 5. Target standard (detail in `11_TARGET_ARCHITECTURE.md`)

1. Per database, nightly `pg_dump -Fc` as a dedicated read-only backup role, plus `pg_dumpall --globals-only`.
2. Per Odoo instance, nightly archive of its filestore, taken in the same job as its dump so the pair is consistent.
3. SQLite stores copied with `sqlite3 .backup` (not `cp`) while the service runs.
4. Configuration: `/etc/nginx`, `/etc/odoo*.conf`, unit files, `/etc/letsencrypt`, each service `.env` — encrypted separately because they hold secrets.
5. Encrypt with `age` or `gpg` to a key that is **not** stored on the VPS; ship to object storage in another provider/region with a write-only credential and object versioning.
6. Retention 7 daily / 4 weekly / 6 monthly.
7. A dead-man's-switch alert: the job pings a monitor on success; silence for 26 hours raises an alert.
8. A monthly restore drill of one production database into an isolated host or container, neutralised, with the result logged.

## 6. Safe verification steps (read-only, need approval to run on the VPS)

```bash
sudo crontab -l; for u in odoo faizy postgres; do sudo crontab -l -u $u; done
systemctl list-timers --all | grep -iE 'backup|dump|certbot'
sudo find / -xdev \( -name '*.dump' -o -name '*.sql.gz' -o -name '*.backup' \) -mtime -30 -printf '%TY-%Tm-%Td %s %p\n' 2>/dev/null | sort
df -h /; sudo du -sh /var/lib/postgresql /var/lib/odoo* /opt/faizy/data 2>/dev/null
```

Plus, in Hostinger hPanel: VPS → Snapshots & Backups — record what is enabled and the date of the newest one.

## 7. What not to do

- Do not start a production dump at peak hours without checking disk headroom first; a full disk stops PostgreSQL for every tenant.
- Do not restore any dump onto this VPS without `odoo neutralize` and without first fixing the cross-database cron polling (F-07), or production workers will run the restored copy's mail and scheduled jobs against real recipients.
