# myfaizy.com

Faizy: a family-care service for Pakistanis abroad. A **separate product** on its own Odoo 19 instance.

| | |
|---|---|
| **Status** | **Production** (reported) |
| **Code on `main`** | [`faizy/`](../../faizy/) — `faizy_core`, `faizy_website`, `faizy_ai`, `faizy_pilot`, docs, deploy scripts. **`main` is the source of truth and is what the VPS runs** (since 22 Nov 2026: PR #194 merged the old production branch, PR #195 the CRM-lead work, and the server checkout was switched to `main` at `200951f`) |
| **Production branch** | None any more. `claude/repo-audit-faizy-instance-fck6o3` was the production branch until 22 Nov 2026; it is fully contained in `main`, nothing tracks it, and it is to be deleted |
| **Database** | `faizy_prod` (PostgreSQL, its own login) |
| **Service** | `faizy-odoo`, own OS user, loopback ports |
| **Deploy** | `faizy/CLAUDE.md` (stop service → `git pull` on `main` → `odoo-bin -u <modules>` → start, chained with `&&`). Last deploy: 22 Nov 2026 19:39 UTC, `-u faizy_core,faizy_pilot`, exit 0, log clean |
| **CI** | `faizy-ci.yml`; the four modules are classified as `venture` in `registry/classification.json` since PR #194 |

## Branch state (22 Nov 2026, evening)

`main` is deployed and verified from the server (owner-run output, 22 Nov 2026 19:40 UTC). `/opt/faizy/src` is on
`main` at `200951f` (the merge of PR #195). The upgrade `-u faizy_core,faizy_pilot` exited 0 and
`/var/log/faizy/odoo.log` shows all four modules loading with no ERROR, CRITICAL or Traceback lines; the service
came back and loaded modules twice more (workers). `ir_module_module` after the upgrade:

| Module | State | Version |
|---|---|---|
| `faizy_core` | installed | 19.0.1.23.0 |
| `faizy_website` | installed | 19.0.1.20.0 |
| `faizy_ai` | installed | 19.0.1.0.0 |
| `faizy_pilot` | installed | 19.0.1.0.0 |

`faizy_pilot`'s first-install hook ran: of the two completed orders, the one with an image is `approved` and the
one without stays `none`, which is the documented behaviour (decision 16a).

The hand edits that used to sit uncommitted on the server (`crm` dependency, `models/crm_lead.py`,
`views/crm_lead_views.xml`) are in `main` via PR #195. The repository copy differs from the old on-disk copy in
one known way: no hard-coded AED prices in the plan-interest labels. Confirm `git status --short` on the server
is empty, so nothing from the old tree is layered on top of `main`.

Open work that edits `faizy/` and has not reached `main`:

| Branch | PR | Base | Note |
|---|---|---|---|
| `claude/faizy-ai-brain` | #140 | `main` | `faizy_ai` 1.1.0 knowledge notes; retargeted from the old production branch on 22 Nov |
| `feat/faizy-hq05-security-guards` | #189 (draft) | `main` | HQ05 PR (a); retargeted on 22 Nov |
| `feat/faizy-hq05-routing-desks` | #190 (draft) | `feat/faizy-hq05-security-guards` | HQ05 PR (b), stacked on #189 |
| `claude/faizy-core-baseline-tests` | none | — | Adds `faizy_core/tests/test_order_baseline.py` (not on `main`); needs a PR against `main` |

Merged and safe to delete (ref deletion is refused from cloud sessions; run `git push origin --delete …` from a checkout, e.g. `/opt/faizy/src` or a workstation clone):
`claude/repo-audit-faizy-instance-fck6o3`, `claude/faizy-crm-lead-fields` (#139 closed as a duplicate of #195),
`faizy/pilot-evidence-gate`, `faizy/pilot-grandfather-existing-evidence`, `claude/faizy-ai-addon`,
`claude/faizy-ai-team-page`. `claude/faizy-document-access` has its Faizy content on `main` but also carries
stale copies of root files; delete it knowingly or leave it.

**Not moved.** Four open branches and three open pull requests edit `faizy/`; moving it now would conflict with all of them. Recommended home: its own private repository.

> Server facts (database, service, checkout commit, upgrade exit code) are **reported** (from owner-run output, Oct–Nov 2026, the latest on 22 Nov 2026) and have not been re-verified from here. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md). Branch facts above were read from the remote on 22 Nov 2026.

## Open points

- Audit ODOO-06 (any signed-in customer could read every family's identity documents) is **fixed in code on `main`**: `rule_document_portal` in `faizy_security.xml` plus six tests, `faizy/docs/00-decisions.md` §15. Whether `-u faizy_core` has been run on `faizy_prod` since is not confirmed from the repo.
- Backups not documented.
- Hand edits on the server have blocked a deploy twice (`faizy/docs/00-decisions.md`, "CRM lead fields captured from live"). Change `/opt/faizy/src` through the repo only.
