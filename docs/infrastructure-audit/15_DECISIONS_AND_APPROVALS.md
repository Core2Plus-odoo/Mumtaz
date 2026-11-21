# 15 — Decisions and Approvals

This is the audit trail. Record each decision here with a name and date before the work starts. As of 2026-11-21 one item has been actioned (PR #127 closed); nothing on any server has been changed.

## 1. What the audit did

| Date (UTC) | Action | Changed anything? |
|---|---|---|
| 2026-11-21 | Read the repository on `main` and all 51 remote branches | No |
| 2026-11-21 | `git fetch --unshallow` in the audit container to scan full history (1,089 commits) for secrets | Local clone only |
| 2026-11-21 | Read GitHub Actions run metadata and the open pull-request list | No |
| 2026-11-21 | One `HEAD` request attempted to each of 11 production hostnames — **all refused by this session's own network policy**; no request reached any server | No |
| 2026-11-21 | Three parallel static code reviews (Odoo addons; C2P Agency OS; all other apps and scripts). Read and grep only | No |
| 2026-11-21 | Wrote the 16 files and the HTML map in `docs/infrastructure-audit/` | Local files only |
| 2026-11-21 | Owner chose "Start batch 1". Closed PR #127. Deleting its branch `claude/html-creation-7knykl` was refused (HTTP 403: the audit session may push only to its own branch) — **branch still exists; owner to delete** | PR state only |
| 2026-11-21 | Owner asked for the repository to be organized website by website. Reorganization **step 1** done in the same pull request: `sites/` index with one folder per website; eight folders with no live deploy dependency moved (`apps/website`, `portal`, `marketplace`, `zaki`, `zaki-ai`, `erp` → `sites/<domain>/`; `apps/platform`, `apps/addons` → `ops/`); seven deploy scripts, one CI job and `docs/ARCHITECTURE.md` updated to the new paths; root `README.md` rewritten. `addons/`, `c2p-delivery-system/` and the Jawhar folders were **not** moved (server-coupled). Mapping table in `sites/README.md` | Repository only |
| 2026-11-21 | Owner instructed that the pack be pushed to the public repository ("It's public, no problem, push"). Committed to branch `ccr-620c243b-p9qlq1` and opened a pull request | Repository (docs only) |

Not done, by design: no SSH, no database connection, no port scan, no login attempt, no exploit test, no load, no change to any setting, credential, DNS record, service or branch.

### Changes on `main` after the audit (recorded at merge time, 21 Nov 2026)

Five pull requests merged to `main` while this pack was in review (#170, #172, #174, #175, #177). They were merged into this branch; the audit findings were **not** re-reviewed in depth. What a quick check shows:

| Finding | State after those merges |
|---|---|
| F-09 (red `main`): flake8 errors | **Fixed** by #170/#172 — `flake8 addons/ tools/scrapers/` is clean |
| F-09: no install test for platform modules | **Addressed** by #172 (fresh-database install CI) |
| ODOO-04 / F-26: finance snapshot open to any logged-in user | **Addressed** by #175 — `/zaki/api/snapshot` now refuses portal users and non-accounting users; tests added |
| ODOO-05 / F-26: portal dashboards read under `sudo()` | **Addressed** by #175 — portal controllers read as the user; tests added |
| `sudo()` overuse | #174 labels every `sudo()` call with its reason and enforces that in CI |
| ODOO-02, ODOO-03 / F-27: RPC-callable group rewrite and Stripe methods | **Still open** — methods are still public |
| ODOO-01 / F-23: shared sign-on secret | **Still open** — `mumtaz_sso` unchanged |
| Repository documentation | #177 added `REPO_MAP.md`, `registry.yaml` and a layering check; `sites/` complements it website by website |

| F-05 / O-04: modules that existed only on the server | **Largely addressed** by #180 (merged later the same day): `c2p_appointment`, `c2p_proposal` and `c2p_master_agent` are now in git "as found", with review item REVIEW-05 open. The 25 database-stored CRM rules (O-03) and the IG2 modules are still outside `main` |

Everything else about the server (F-01, F-02, F-04, F-06 to F-08 and the rest) is unchanged by these merges. #179 (Jawhar site and design work) does not touch any audit finding.

## 2. Decisions needed

| ID | Decision | Options | Recommendation | Owner | Status |
|---|---|---|---|---|---|
| **D-01** | Where does this audit pack live? The repository is public | (a) make the repo private, then commit · (b) keep the pack out of git (private drive / vault) · (c) commit only a redacted summary | (a), and until then (b) | Business owner | **Decided 2026-11-21 by the owner: commit to the public repository as-is.** The auditor's recommendation was (a)/(b) |
| **D-02** | Named business owner and technical owner for each system (C2P CRM, Platform ERP, IG2, Faizy, Jewel, Pharma, Agency OS, WordPress sites, each domain) | — | One name each; record in `infra/INVENTORY.md` | Business owner | **Open** |
| **D-03** | How does the audit get server evidence? | (a) owner runs the read-only V-pack script and pastes output · (b) a read-only SSH account for the auditor · (c) attach the server to a session | (a) — it is how the Pharma work was done and keeps credentials with the owner | Business owner | **Open** |
| **D-04** | Second small VPS for staging/demo? | yes / no | Yes — it removes the production/non-production mixing at low cost | Business owner | Open |
| **D-05** | Backup destination, and who holds the decryption key | Object storage provider; key in a password manager held by two people | Different provider from the VPS; two key holders | Business owner | **Open** |
| **D-06** | What should `backup.yml` and `deploy-production.yml` do once PR #168 makes them runnable? | (a) disable both until redesigned · (b) let them run as written | (a) — as written they target a stack that does not exist and report success regardless | Tech lead | **Open** |
| **D-07** | IG2: the client's accounting system is reached over plain HTTP on a raw port. Tell the client? Agree a window to move to HTTPS? | — | Yes to both; agree a date and the new URL | Business owner | **Open** |
| **D-08** | ZAKI, customer portal, marketplace, "platform rebuild": which are real products going forward? | keep one ZAKI implementation and fix it · retire all until there is demand | Retire until a decision — neither ZAKI backend is safe to expose as written, and the portal's backend source is gone | Business owner | Open |
| **D-09** | Stray databases: `mumtaz_erp`, `IG2`, `Mumtaz_C2P_staging`, `scratch_pre`, `mumtaz_platform` — keep, archive or drop, per name | — | Archive (dump off-site), revoke connections for a week, then drop | Business owner, per database | Open |
| **D-10** | PR #127 / branch `claude/html-creation-7knykl`: an HTML replica of a bank payment instrument with a signature area and no "specimen" marking, on a public branch | close and delete · keep with clear specimen marking in a private repo | Close and delete | Business owner | **PR closed 2026-11-21; branch deletion pending (owner)** |
| **D-11** | Recovery objectives (proposed in `09` §3: 24 h RPO, 8 h RTO for client and customer systems) | accept / change | Accept as a start | Business owner | Open |
| **D-12** | WordPress content sites on the same host as client ERPs? | same host · separate cheap hosting | Separate — a WordPress compromise should not sit next to client ledgers | Business owner | Open |
| **D-13** | Are the scraper and its harvested contact data still wanted, and on what lawful basis are scraped contacts emailed? | — | Legal/compliance view before further use | Business owner | Open |

## 3. Approval log for remediation batches

No batch may start without a row here. Copy the template row per batch.

| Batch | Scope (IDs) | Systems | Backup reference | Window | Approved by | Date | Result | Rollback used? |
|---|---|---|---|---|---|---|---|---|
| 2A | S-01, S-02, D-10 | GitHub repo; Odoo admin accounts | n/a | any time | Owner ("Start batch 1") | 2026-11-21 | D-10: PR closed, branch not yet deleted. S-01, S-02 and the V-pack: pending, owner-run | — |
| 2B | B-01, B-02, B-03 | All production databases (read-only dumps) | this batch creates it | off-peak | — | — | — | — |
| 2C | S-03, S-04, S-05 | IG2; firewall | 2B | agreed with client | — | — | — | — |
| 2D | S-06, S-07, O-01, O-02 | `odoo2`, `odoo3`, `odoo`/`odoo4`, nginx | 2B | off-peak | — | — | — | — |
| 2E | S-08 … S-11 | Agency OS, nginx | 2B | any time | — | — | — | — |

## 4. First batch proposed for approval

**Batch 2A + the read-only verification pack.** Nothing in it restarts a service or changes what any user sees.

1. **V-pack (read-only).** The owner runs one script on the VPS that prints host facts, listening ports, firewall rules, nginx hostname → upstream map, unit files, masked Odoo configs, git state of each checkout, database metadata, timers/crons and certificate dates. Passwords are masked by the script. Output is pasted back; nothing is written on the server.
2. **S-01 — make `Core2Plus-odoo/Mumtaz` private.** Before flipping visibility, add a read-only deploy key (or fine-grained token) to each server checkout that pulls from GitHub, so `update.sh` and the Faizy/Pharma/Jewel pulls keep working. Validation: `git ls-remote origin` succeeds on each checkout; an anonymous clone fails.
3. **S-02 — replace any default-strength Odoo administrator login password** on every instance, starting with whichever one earlier sessions flagged. This is a user-password change inside Odoo; it needs no restart. Store the new values in the vault. (The `admin_passwd` master password in each config file is handled in batch 2D, because changing it needs a restart.)
4. **D-10 — close PR #127 and delete its branch.**

Why this batch first: it removes the public description of how to reach the systems and the weakest credential, and it produces the evidence every later step depends on — without touching a running service.

**Status:** batch 2A approved by the owner on 2026-11-21. Outstanding from the owner: delete branch `claude/html-creation-7knykl`; S-01; S-02; run the V-pack; choose D-03; name the owners in D-02.
