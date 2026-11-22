# myfaizy.com

Faizy: a family-care service for Pakistanis abroad. A **separate product** on its own Odoo 19 instance.

| | |
|---|---|
| **Status** | **Production** (reported) |
| **Code on `main`** | [`faizy/`](../../faizy/) — `faizy_core`, `faizy_website`, `faizy_ai`, `faizy_pilot`, docs, deploy scripts. **Since 22 Nov 2026 `main` is the source of truth**: PR #194 merged the production branch into it, so `faizy/` is identical on both |
| **Production branch** | `claude/repo-audit-faizy-instance-fck6o3`. The VPS still tracks it. 0 commits ahead of `main`, 167 behind; it should be fast-forwarded to `main` or the VPS repointed to `main`, after which it can be deleted |
| **Database** | `faizy_prod` (PostgreSQL, its own login) |
| **Service** | `faizy-odoo`, own OS user, loopback ports |
| **Deploy** | `faizy/CLAUDE.md` on `main` (stop service → `git pull` → `odoo-bin -u <modules>` → start, chained with `&&`) |
| **CI** | `faizy-ci.yml`; the four modules are classified as `venture` in `registry/classification.json` since PR #194 |

## Branch state (22 Nov 2026)

What `main` holds is what production runs, with one known difference. The server working tree at
`/opt/faizy/src` carries uncommitted hand edits in `faizy_core` (a `crm` dependency, `models/crm_lead.py`,
`views/crm_lead_views.xml`). Those were captured into git on 3 Nov 2026 on branch `claude/faizy-crm-lead-fields`
and are being merged to `main` in PR #195. Until that merges, `git pull` on the server will refuse because
`__manifest__.py` and `models/__init__.py` are locally modified. After it merges, reset the server tree to the
repository state rather than keeping the local edits: the repo version removed hard-coded AED prices from the
plan-interest labels that the on-disk copy probably still has.

Open work that edits `faizy/` and has not reached `main`:

| Branch | PR | Base | Note |
|---|---|---|---|
| `claude/faizy-crm-lead-fields` | #195 (via `claude/nifty-archimedes-oj6nmn`) | `main` | CRM lead fields from live; supersedes #139 |
| `claude/faizy-crm-lead-fields` | #139 | production branch | Same content as #195; close once #195 merges |
| `claude/faizy-ai-brain` | #140 | production branch | `faizy_ai` 1.1.0 knowledge notes; retarget to `main` |
| `feat/faizy-hq05-security-guards` | #189 (draft) | production branch | HQ05 PR (a); retarget to `main` |
| `feat/faizy-hq05-routing-desks` | #190 (draft) | `feat/faizy-hq05-security-guards` | HQ05 PR (b), stacked on #189 |
| `claude/faizy-core-baseline-tests` | none | — | Adds `faizy_core/tests/test_order_baseline.py` (not on `main`); needs a PR against `main` |
| `claude/faizy-document-access` | none | — | Content already on `main` (ODOO-06 fix); branch can be deleted |

**Not moved.** Six open branches and five open pull requests edit `faizy/`; moving it now would conflict with all of them. Recommended home: its own private repository.

> Server facts (database, service, working-tree state) are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified from here. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md). Branch facts above were read from the remote on 22 Nov 2026.

## Open points

- Audit ODOO-06 (any signed-in customer could read every family's identity documents) is **fixed in code on `main`**: `rule_document_portal` in `faizy_security.xml` plus six tests, `faizy/docs/00-decisions.md` §15. Whether `-u faizy_core` has been run on `faizy_prod` since is not confirmed from the repo.
- Backups not documented.
- Hand edits on the server have blocked a deploy twice (`faizy/docs/00-decisions.md`, "CRM lead fields captured from live"). Change `/opt/faizy/src` through the repo only.
