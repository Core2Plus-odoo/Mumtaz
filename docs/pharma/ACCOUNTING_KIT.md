# Accounting for Odoo 19 Community: third-party kit, review and hardening

Status: **fetched, reviewed, hardened, tested on throwaway databases (vendor suite 83/83, combined 62/62) and INSTALLED in the staging database `mumtaz_pharma` on 2026-11-18 (103 modules). Production: not in scope.**
Owner approved proceeding on 2026-11-18 with: hardening module, throwaway-database tests first, live install gated.

## Why

Odoo 19 Community's `account` is invoicing. Financial reports, asset management, budgets, bank statement import,
post-dated cheques and follow-ups are Enterprise (`account_accountant`) features. The Cybrosys page
(https://www.cybrosys.com/odoo/industries/accounting-and-finance/) is a service page and names no download; its feature list
matches Cybrosys's free Community kit, which has a 19.0 branch on GitHub.

## What was fetched (source only, in a sandbox, not in this repository)

| | |
| --- | --- |
| Repository | https://github.com/CybroOdoo/cybroaddons, branch `19.0` |
| Pinned commit | `fdeea97df75b7b45a6ed0f9af3c0e9850399f517` (2026-11-13, message "[ADD] Initial Commit") |
| `base_accounting_kit` | 19.0.3.3.1, LGPL-3, 328 files, 80 tests, depends `account`, `sale`, `account_check_printing`, `analytic`, `contacts`, `base_account_budget`, `cybrosys_support_client`; python packages `openpyxl`, `ofxparse`, `qifparse`, `xlsxwriter` |
| `base_account_budget` | 19.0.1.0.2, LGPL-3, depends `base`, `account`, `cybrosys_support_client` |
| `cybrosys_support_client` | 19.0.1.1.0, LGPL-3, depends `base`, `web` |

The vendor code is **not vendored into this repository**. The VPS fetches the pinned commit into `/opt/thirdparty/cybroaddons`
(`stage.sh thirdparty`), outside every Mumtaz checkout, and only `odoo-pharma` reads it.

## Review findings (static read of the three modules)

| # | Severity | Finding | Mitigation here |
| --- | --- | --- | --- |
| 1 | **S2** | `/xlsx_report` (auth user, POST, csrf off) takes `model` from the request, runs it `.sudo()` and calls `get_xlsx_report`. No access check. Any authenticated user, a portal user included, can stream ledgers and partner statements. Reachable models: `account.report.xlsx.mixin` and its wizards, `res.partner`. | `pharma_accounting_hardening` subclasses the controller: caller must hold `account.group_account_user` or the kit's `group_account_chief` (the groups the kit uses for its own report menus), and `model` must really implement `get_xlsx_report`. Otherwise 403. |
| 2 | **S2** (data protection) | `cybrosys_support_client` is a hard dependency of the kit and the budget module, never used by their code. Every internal user may open its form (group `base.group_user`, full CRUD). On submit it POSTs name, email, phone, free text and up to five attachments to `support.cybrosys.com`. Nothing is sent automatically (no cron, no startup call, no database id in the payload). A shared token is hard-coded in the source (not reproduced here). | Access row re-pointed to `base.group_system`; endpoint parameter forced to a dead loopback address on every upgrade (an empty value would fall back to the vendor URL, so it is not left empty). |
| 3 | S3 | `security.xml` rewrites core records `account.group_account_invoice`, `account.group_account_user`, `account.group_account_manager` (names, sequence, implied groups) and makes the core Administrator group and the new Chief Accountant group imply each other; it also adds the root and admin users to both. Modifying standard records is against the standard-first rule. | Accepted for a staging demo; the vendor and combined tests must show it is harmless. Revisit before production. |
| 4 | S3 | The 19.0 branch is five days old with one commit. No field history on Odoo 19. | Vendor tests on a throwaway database first (`test-kit`). |
| 5 | S3 | Reports use raw SQL (`cr.execute`) in many places, mostly parameterised; one concatenates an ORM-generated clause. `sudo()` used for follow-up mail and attachments. | Noted, not changed. |
| 6 | S4 | Excel route keeps `csrf=False`; the vendor front end posts without a token and the route only produces a download. | Not changed. |

Checked and clean: no outbound HTTP other than the support form; no `eval`, `exec`, `pickle`, `subprocess`; hard-coded URLs are
copyright headers and a demo-site link in the manifest.

Interplay: the kit overrides `account.move.action_post` and calls `super()` first, so the tax gate (in `_post`) still fires.
This is asserted by two tests in the hardening module, not assumed.

## Residual risks after hardening

- After the checks, the export still runs as superuser. Correct for accountants in a single-company database. **In a
  multi-company database an accountant restricted to one company could export another company's report.** Review before a second company exists.
- The vendor support button (top-bar headset icon with its Alt+Shift+H hotkey, and the user-menu item) is removed from the web client by `pharma_accounting_hardening` 19.0.1.1.0. The access and endpoint controls stay as defence in depth, because the form model still exists.
- The kit installs scheduled actions (follow-ups, recurring entries, bank auto-reconcile). `install-accounting` re-runs `odoo neutralize` so they stay off on staging.
- Python packages are installed with `pip --target /opt/thirdparty/pydeps` and added to `odoo-pharma` only; no system package changes, other tenants are unaffected.

## Test plan (all on throwaway databases, before the live install)

| Step | Command | Expect |
| --- | --- | --- |
| 1 | `stage.sh thirdparty` | pinned commit checked out, three modules with versions and LGPL-3 |
| 2 | `stage.sh deps` (gate: pip into an isolated folder) | four python packages importable by the odoo user |
| 3 | `stage.sh test-kit` | the vendor's own tests, in a database without our modules, `0 failed, 0 error(s)`. **Done: 83 of 83 pass.** |
| 4 | `stage.sh test-combined` | our tests with the kit and the hardening module installed: 54 + 8 = 62, `0 failed, 0 error(s)`. **Done: 62 of 62 pass** (first run 61 of 62; the failure was a naive text check in one of my tests, fixed). |

## Live install (gate: needs the owner's go after steps 1 to 4 are green)

`stage.sh install-accounting`: dumps `mumtaz_pharma`, installs the four modules with the CLI configuration, re-runs neutralize,
adds the kit folder to `/etc/odoo-pharma.conf` and `PYTHONPATH` to the unit, restarts **`odoo-pharma` only**, verifies.
Rollback (printed by the script): stop the unit, restore the dump, `stage.sh accounting-off`.

## Not done, on purpose

- Nothing from the vendor is committed to this repository.
- No other Cybrosys module (dynamic reports, dashboards, cash-flow statements) was reviewed; each would need the same review.
- Production: not in scope. Findings 3 and the multi-company note must be resolved first.
