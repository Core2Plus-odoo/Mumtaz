# 10 — Risk Register

Ranked by severity, then by how directly the finding exposes data or prevents recovery. **Nature** distinguishes *Confirmed* (verified in the repository), *Reported* (owner-run server output recorded in the repo; not re-verified), and *Suspected*. Every item's remediation status is **Open — nothing has been changed**.

Action IDs point to `13_REMEDIATION_BACKLOG.md`. Effort: S ≤ 2 h · M ≤ 1 day · L > 1 day.

## Critical

| ID | Finding | Project | Nature · Evidence | Business impact | Consequence | Likelihood | Action | Effort | Depends on | Approval | Verify by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **F-01** | Odoo ports reachable from the internet; client ledger used over plain HTTP on `IP:8071`; a default-strength administrator login reported on a reachable instance | IG2, C2P, ERP | Reported · `docs/erp/00-current-system-audit.md` (branch), `docs/project/01-AS-IS-AUDIT.md` §3.6 (branch), `apps/website/*.html` links | Disclosure or alteration of a client's accounting records; breach of client contract; loss of the CRM | Credential interception; unauthorised login; database-manager abuse | **High** — the address and the weakness are published (F-03) | S-02, S-03, S-04, S-05, S-09 | M | V-02, V-03, V-11; client notice (D-07) | Owner | External check shows only 22/80/443; login over HTTPS only |
| **F-02** | No verified, off-host backup of any production database, filestore or SQLite store; the nightly job has never run | All production | Confirmed (repo, Actions history) · server NV | Permanent loss of client ledger, CRM, customer identity documents, engagement history | No recovery from disk loss, bad upgrade, deletion or ransomware | Medium (certain over a long enough period) | B-01 … B-07 | M then L | D-05 | Owner | A restore drill succeeds for each database |
| **F-03** | Public repository publishes server address, port map, database names, client and staff details, and a note that a weak credential exists | All | Confirmed · `list_repos` visibility; locations in `04` §A3 | Enables F-01; confidentiality breach toward a client; reputational | Targeted attack with full reconnaissance already done | **High** | S-01 | S | Deploy credential on server checkouts | Owner | Anonymous clone fails; server pulls still work |
| **F-23** | One SSO secret copied into every tenant database lets any tenant administrator sign in to any other tenant | Mumtaz Platform | Confirmed in code (ODOO-01) · live exposure depends on installed modules | Cross-customer data breach in the SaaS | Full takeover of other tenants' ERP | Medium (needs a tenant admin; trivial once one exists) | A-09 | M | V-11 (is `mumtaz_sso` installed anywhere?) | Tech lead | Token for DB A rejected on DB B in a test |
| **F-24** | ZAKI FastAPI backend: any tenant's finances readable and knowledge base writable with no authentication | ZAKI (platform rebuild) | Confirmed in code (APP-01, -02) · deployment NV | Cross-customer financial disclosure; poisoned AI advice | Read by integer id; persistent prompt injection | High **if** the service is reachable; none if not deployed | S-11, A-14 | S to block, L to fix | V-06 | Owner | Port 8001 not listening or not proxied |

## High

| ID | Finding | Project | Nature · Evidence | Business impact | Likelihood | Action | Effort | Approval | Verify by |
|---|---|---|---|---|---|---|---|---|---|
| **F-04** | Production runs from an unmerged feature branch; duplicate checkouts shadow each other; `/opt/mumtaz/addons` not on the addons path | C2P, ERP, IG2 | Reported · `docs/pharma/DEPLOY_LOG.md`, as-is audit | Nobody can say what code production runs; fixes merged to `main` never arrive | Certain | R-05, R-11 | L | Owner | `git status` on server shows a tag of `main` |
| **F-05** | Business logic outside version control: 25 server actions in the CRM database, one installed module with no source, modules untracked on the server | C2P | Reported · `c2p-delivery-system/docs/07-…` | Unreviewable rules act on 41k contacts; unexplained archive of 29k leads already happened | Certain | O-03, O-04 | L | Owner | Actions exported into a module; module list matches git |
| **F-06** | One PostgreSQL role and one OS user shared by C2P, ERP, the client's ledger and staging | C2P, ERP, IG2, Pharma | Reported | A fault in any instance reaches every database | Medium | R-13 | L | Owner | Cross-role connection refused |
| **F-07** | Wrong or duplicate instance↔database wiring: two servers on `Mumtaz_C2P`; cron workers of `odoo2`/`odoo3` open every database; prefix `dbfilter`; `erp.` longpolling routed to the Jewel container | C2P, ERP, IG2, Jewel | Reported (cron polling observed) / Suspected (duplicate) | Jobs run twice or under the wrong code; a client's process touches other tenants' databases; restores contaminate production | High | S-06, S-07, O-01 | M | Owner | `pg_stat_activity` shows one application per database |
| **F-08** | Client production system has no staging, no TLS, and its code lives only on an unmerged branch | IG2 | Reported | Every change is tested on the client's live books | Certain | S-03, R-05, R-15, A-13 | L | Owner + client | Staging twin exists; change log shows staging first |
| **F-09** | CI/CD not functional: four workflow files invalid, `main` red, secret scan failing, 39 of 53 modules untested, deploy pipeline targets a stack that does not exist | All | Confirmed · Actions API | Defects and secrets reach production unchecked; false sense of a backup and deploy process | Certain | R-03, R-04, O-09 | M | Tech lead | `main` green; required checks enforced |
| **F-10** | A server note dated 2026-11-20 says `mumtaz.digital` "lapsed", while a certificate was issued for a subdomain two days earlier | All `*.mumtaz.digital` | Reported, contradictory | If the registration lapses, ten sites and all certificate renewals fail together | Unknown | V-10 | S | — | Registrar shows expiry date and auto-renew |
| **F-11** | Orphaned services: `erp-server` crash-looping; `zaki-server` source deleted but still routed by templates, holding Odoo admin credentials and the user registry | Portal, ZAKI, Marketplace | Reported / Confirmed (deletion in `48a2cf9`) | Unmaintained code with privileged credentials may still face the internet | Medium | O-02, S-11, D-08 | S | Owner | `systemctl` and `ss` show them stopped, or a decision to restore source |
| **F-15** | Third-party accounting kit in the client database without the hardening written for Pharma (unguarded export route; form that can send data to the vendor) | IG2 | Reported · `deploy/pharma-staging/README.md` | Unauthenticated export of financial reports from a publicly reachable instance | Medium–High given F-01 | A-13 | S–M | Owner + client | Anonymous `POST /xlsx_report` refused |
| **F-25** | Identity documents readable by every Faizy portal user | Faizy | Confirmed in code on the production branch (ODOO-06) | Disclosure of customers' CNIC/passport scans | Medium | A-10 | S | Owner | Portal user sees only own documents |
| **F-26** | Any logged-in user can read all-company financials (`/zaki/api/snapshot`, `/app*`) | Mumtaz Platform | Confirmed (ODOO-04, -05) | Cross-company disclosure inside a shared database | Medium | A-11 | M | Tech lead | Portal user gets 403 |
| **F-27** | Any logged-in user can rewrite group membership or call Stripe with the platform key over RPC | Mumtaz Platform | Confirmed (ODOO-02, -03) | Privilege escalation; unwanted charges | Medium | A-11 | S | Tech lead | RPC call refused |
| **F-28** | C2P Agency OS: authentication is opt-in and fails open; stored Odoo key and GitHub token can be redirected to another host; path traversal on push; unescaped branding HTML | Agency OS | Confirmed in code (C2P-01 … -05) · production mode NV | Loss of the admin-grade Odoo key for the CRM; code pushed to the addons repo; client data disclosure | Low behind working auth; High without | S-08, A-03 … A-06 | S to verify, L to fix | Owner | Service refuses to start without an auth mode; tests |
| **F-29** | Literal credentials and fallback secrets in scripts in a public repo; WordPress installer leaves admin setup unclaimed; Faizy installer exposes Odoo with the default login on :8080 until changed | Legacy scripts, WordPress, Faizy | Confirmed (APP-03, -04, -11) | Takeover at install time; reuse of a published password | Low–Medium (depends on past use) | S-12, A-17 | S | Owner | Scripts abort on defaults; rotation recorded |
| **F-30** | Other High code findings: marketplace listings writable across companies (ODOO-08); demo module publishes client sign-in codes if installed (ODOO-07); stored XSS in portal/ERP/ZAKI front ends with tokens and API keys in `localStorage` (APP-06 … -08); SSRF in `zaki-ai` (APP-05); superuser DB role and single admin login in the platform rebuild (APP-09, -10) | Platform, Jewel, legacy apps | Confirmed in code | Varies; several are in code that should be retired rather than fixed | Low–Medium | A-12, A-14, A-16 | M–L | Tech lead | Per item |

## Medium

| ID | Finding | Project | Nature | Action | Effort |
|---|---|---|---|---|---|
| F-12 | Nine competing nginx definitions, five Odoo configs, six database-name defaults; nothing in the repo can rebuild the server | All | Confirmed | R-02, R-12 | M |
| F-13 | Stray databases of unknown ownership, one a copy of real CRM data owned by `postgres` | PostgreSQL | Reported | R-16 | S each |
| F-14 | A restored production copy emails real contacts and runs crons unless neutralised | C2P | Reported | B-06, O-08 | S |
| F-16 | Pipeline hygiene: action pinned to a moving branch; workflow input injected into a remote shell; long-lived SSH key; rollback restores no data | CI | Confirmed | O-07 | M |
| F-17 | No monitoring or alerting of any kind | All | Confirmed absent | O-05 | M |
| F-18 | Certificate expiry and TLS settings unknown for every host but one | All sites | NV | V-10 | S |
| F-19 | Replica of a bank payment instrument with a signature area and no specimen marking on a public branch (PR #127) | Repo | Confirmed | D-10 | S |
| F-20 | Secrets handling: plaintext files, one DB password copied across instances, no inventory or rotation, provider tokens and a tax-authority private key in plaintext database fields | All | Confirmed / Reported | S-12 | L |
| F-21 | Odoo from the nightly package repository; unattended upgrades in one installer | All native Odoo | Reported / Confirmed | O-10 | S |
| F-22 | E-invoicing reports false status (auto-"rejected" after 24 h; sandbox "accepted" without a call); no tests | Mumtaz Platform | Confirmed (ODOO-19) | A-12 | L |
| F-31 | Unthrottled anonymous write endpoints (lead API, org signup, Faizy signup) | Platform, Faizy | Confirmed | A-12, S-10 | M |
| F-32 | Stripe webhook swallows errors; amounts not verified; zero-decimal currency bug | Platform | Confirmed (ODOO-18) | A-12 | M |
| F-33 | 65 models without record rules; applicant PII readable by all internal users | Platform | Confirmed (ODOO-14) | A-12 | M |
| F-34 | Kiosk sends body measurements with name and phone while on-screen copy says nothing is sent; voice vendor receives fit data | Jewel | Confirmed (APP-22) | A-16 | S |
| F-35 | Scraper ignores robots.txt, spoofs a browser, harvests contact data into CSV and CRM | Tools | Confirmed (APP-29) | D-13 | S |
| F-36 | Unpinned dependencies; `cryptography` missing; outdated browser libraries without SRI | Agency OS, apps | Confirmed | A-15 | M |
| F-37 | WordPress on the same host as client ERPs; installer hardening gaps | Sites | Confirmed (script) / NV (deployed?) | D-12, A-17 | M |
| F-38 | Destructive legacy scripts: `rsync --delete` into a path that may hold the repo; cutover script that deletes then aborts | Legacy | Confirmed (APP-25, -26) | R-08 | S |
| F-39 | Agency OS: SSRF, no login rate limit, prompt-injection-to-action gaps, non-atomic approvals, no store backup | Agency OS | Confirmed (C2P-09 … -14) | A-05 … A-08 | L |

## Low

| ID | Finding | Action |
|---|---|---|
| F-40 | 51 branches, 12 open PRs, two stranded security fixes, no tags | R-17, A-01, A-02 |
| F-41 | Stale and contradictory documentation; three `CLAUDE.md` files with conflicting rules | R-02 |
| F-42 | 31 MB of model binaries in git; single-file applications of 250–400 KB | R-09 |
| F-43 | `list_db = True` on Jewel staging (deliberate, behind an allow-list) | Accept; re-check when moved |
| F-44 | Odoo 19 API drift; missing hard dependencies; inert record rules; dead code | A-12 |
| F-45 | `.env.example` ships weak defaults; demo passwords documented | S-12 |
| F-46 | Google Fonts requested from every ERP backend page | A-12 |

## Urgent escalation set

Per the brief, publicly exposed credentials, cross-client exposure and missing recovery are escalated immediately: **F-01, F-02, F-03** (and **F-07**, **F-15**, **F-25** as cross-client or customer-data exposure). None has been touched. The first batch proposed for approval is in `15_DECISIONS_AND_APPROVALS.md` §4.
