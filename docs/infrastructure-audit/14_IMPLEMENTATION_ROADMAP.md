# 14 — Implementation Roadmap

Phases follow the brief. Each phase ends with an explicit gate; nothing in a later phase starts before the gate of the one before it is signed in `15_DECISIONS_AND_APPROVALS.md`. IDs refer to `13_REMEDIATION_BACKLOG.md` (V = verification, S = security, B = backup, O = operations, A = application) and `12_REORGANIZATION_PLAN.md` (R = restructuring).

Effort is working time for one engineer who has server access; calendar time depends on approvals and maintenance windows.

## Phase 0 — Discovery (in progress)

| Step | State |
|---|---|
| Repository, history, branches, CI, open PRs | **Done** (this pack) |
| Static security review of all code on `main` | **Done** |
| Server, databases, DNS, certificates, firewall | **Blocked — no access.** Needs the read-only verification pack V-01 … V-12 |
| Ownership per system | **Blocked — needs the owner** (D-02) |

**Gate 0:** V-01 … V-12 output received and `infra/INVENTORY.md` written from it. Until then, every "R-doc" and "NV" item in this pack stays unconfirmed.

Effort: 0.5 day to run and read; 0.5 day to write up.

## Phase 1 — Risk assessment

| Step | Output |
|---|---|
| Re-rate every finding in `10_RISK_REGISTER.md` against V-pack evidence | Confirmed / downgraded / closed |
| Decide owners, RPO/RTO, backup destination | D-02, D-05, D-11 |
| Decide what to tell the IG2 client | D-07 |

**Gate 1:** risk register re-issued with "Confirmed on host" status; Phase 2 batches approved one by one.

Effort: 0.5 day.

## Phase 2 — Immediate security remediation

Batches are ordered so that the first ones change nothing a user can notice.

| Batch | Content | User-visible impact | Rollback |
|---|---|---|---|
| **2A — Contain disclosure** | S-01 make the repository private (after server checkouts have a read credential); S-02 change any default-strength Odoo administrator password (no restart); close PR #127 (D-10) | None | Visibility can be reverted; passwords are in the vault |
| **2B — First real backups** | B-01 check disk headroom; B-02 one-off dump of each production database + filestore + SQLite stores + config bundle, off-peak, copied off the host; B-03 restore one of them on an isolated machine | Brief extra load during dumps | Nothing to roll back |
| **2C — Close exposed ports** | S-03 put IG2 behind nginx + TLS on its hostname, tell its users the new URL, then bind `odoo3` to loopback and remove the firewall rule; S-04 same check for every other application port; S-05 default-deny at the provider firewall | IG2 users switch URL (announce first); one restart of `odoo3` (~1 min) | Re-open the port; revert the `http_interface` line |
| **2D — Stop cross-database behaviour** | S-06 add `db_name` to `odoo2` and `odoo3`; S-07 resolve the two servers on `Mumtaz_C2P`; O-01 fix the `erp.` longpolling upstream and the dead `ig2.` websocket upstream; O-02 disable the crash-looping `erp-server` unit | One restart each of `odoo2`, `odoo3` (~1 min, scheduled) | Remove the added line; restart |
| **2E — Application gates** | S-08 confirm the C2P Agency OS runs with an auth mode and a secret key; S-09 `location ~ ^/web/database { deny all; }` on every Odoo vhost; S-10 nginx rate limit on login endpoints; S-11 make sure neither ZAKI backend is publicly reachable until fixed | None expected | Remove the nginx lines; reload |

**Gate 2:** each batch has its own approval line, backup reference, validation result and rollback note recorded. External check from outside the VPS shows only 22/80/443 open.

Effort: 2A 1 h · 2B 0.5–1 day · 2C 0.5 day + client notice period · 2D 0.5 day · 2E 0.5 day.

## Phase 3 — Repository organization

| Step | Refs |
|---|---|
| Fix invalid workflows safely; green `main`; branch protection | R-03, R-04 |
| Delete merged branches; triage open PRs; merge the two stranded security fixes after review | R-17, A-01, A-02 |
| Reconcile the production branch into `main`; recover untracked modules and database-stored server actions into git | R-05, O-03, O-04 |
| Split Faizy, Pharma, IG2, WordPress into their own repositories | R-06, R-07 |
| Archive legacy/orphaned code | R-08 |
| Restructure into `products/*` + `infra/` | R-09, R-10 |

**Gate 3:** `main` is green and protected; production can be rebuilt from tagged commits; no production code exists only on the server.

Effort: 4–6 days, mostly R-05.

## Phase 4 — Infrastructure standardization

| Step | Refs |
|---|---|
| Automated nightly encrypted off-site backups with heartbeat; monthly restore drill | B-04 … B-07 |
| Monitoring: uptime, wrong-database check, certificates, domain, disk, backup heartbeat | O-05 |
| nginx from templates with shared security headers | R-12 |
| Per-application database roles and OS users; hardened unit files | R-13 |
| Staging host; move Jewel and Pharma; create staging twins for C2P, ERP, IG2 | R-15 |
| Archive and drop stray databases | R-16 |
| Secrets inventory and rotation of everything copied between configs | S-12 |
| Optional renames | R-14 |

**Gate 4:** a restore drill has succeeded for every production database; an alert has fired and been acknowledged in a test; each instance connects with its own role.

Effort: 6–8 days.

## Phase 5 — Application stabilization

| Step | Refs |
|---|---|
| C2P Agency OS: fail-closed auth, secret-handling fixes, path and HTML escaping fixes, tests in CI | A-03 … A-08 |
| Odoo platform: public-route review fixes, access-rule gaps, tests for untested modules that are actually installed | A-09 … A-12 (see `06_ODOO_INSTANCES_AUDIT.md`) |
| IG2: apply the accounting-kit hardening already written for Pharma; add a staging twin to its change path | A-13 |
| ZAKI / portal / marketplace: product decision, then rebuild one or retire all | D-08, A-14 |
| Dependency pinning and lockfiles | A-15 |
| Jewel: privacy copy and consent for fit data; confirm one-time-code behaviour in production mode | A-16 |

**Gate 5:** no Critical or High application finding open on a system that is reachable from the internet.

Effort: 8–12 days, depending on D-08.

## Phase 6 — Deployment modernization

| Step | Refs |
|---|---|
| Release tags; per-product deploy script on the `stage.sh` pattern; per-product `DEPLOY_LOG.md` | R-11, O-06 |
| GitHub Environments with required reviewers per product; restricted deploy keys | O-07 |
| Staging-first rule enforced by the deploy script (refuses production if the tag has not passed staging) | O-08 |
| Path-filtered CI per product | O-09 |

**Gate 6:** one full release of each product has gone dev → CI → staging → approval → production through the new path, including a rehearsed rollback.

Effort: 4–5 days.

## Phase 7 — Validation and handover

| Check | Evidence |
|---|---|
| Availability | 14 days of monitor history per site |
| Data integrity | Row counts and module lists before/after each migration, kept in the deploy logs |
| Security | External port scan of the VPS **by the owner or with written authorisation** shows 22/80/443 only; findings re-tested |
| Backups | Restore-drill log for every production database |
| Rollback | One rehearsed rollback per product |
| Documentation | `infra/RUNBOOK.md` followed by someone other than its author to rebuild a staging instance |
| Access | List of who holds SSH, GitHub admin, Hostinger, registrar and vault access |

**Gate 7:** sign-off by the business owner; remaining Medium/Low items moved to a standing backlog.

Effort: 2 days plus the 14-day observation window.

## Summary

| Phase | Effort | Production restarts | Needs from the owner |
|---|---|---|---|
| 0 | 1 day | 0 | Run V-pack or grant read-only SSH; name owners |
| 1 | 0.5 day | 0 | Decisions D-02, D-05, D-07, D-11 |
| 2 | 2.5–3 days | 3 short, scheduled | Approval per batch; client notice for IG2 |
| 3 | 4–6 days | 0–1 | Approvals for visibility, splits, archive |
| 4 | 6–8 days | 1 per instance, scheduled | Second host budget; backup storage |
| 5 | 8–12 days | per release | Product decisions |
| 6 | 4–5 days | per release | Reviewers named |
| 7 | 2 days + 14-day watch | 0 | Sign-off |

Rules that hold throughout: one product per maintenance window; a fresh backup before every change; no unrelated production changes in one deployment; nothing destructive without a named approval.
