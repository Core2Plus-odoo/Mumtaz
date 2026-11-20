# Decision register

Open decisions that require the business owner. Each states what is blocked and
what the architect recommends. Nothing below has been decided or assumed away.

Status: `OPEN` · `DECIDED` · `SUPERSEDED`

---

## DEC-001 — What is actually installed, where? **[OPEN] [BLOCKS WAVES 1–2]**

**Question.** For each of the five Odoo instances on the production VPS: which
database does it serve, what is its `dbfilter`, and which of the 38 modules in
`addons/` is installed in each?

**Why it blocks.** Three separate conclusions in this audit are undecidable
without it:

1. Whether 40 models with no `ir.rule` constitute a data leak or are correctly
   isolated by the database boundary (`SECURITY_MATRIX.md` §1).
2. Whether any refactor — consolidating the eight scaffolding modules, migrating
   `media.plan` onto `sale.order` — is a code change or a data migration.
3. Whether `c2p_master_agent`, which prior inspection found **installed with no
   source in any checkout**, is load-bearing.

**Also unresolved from prior sessions:** production has two identical 37-module
checkouts plus a third, and `/opt/mumtaz/addons` is not on the `addons_path`. So
`addons/` in git is not demonstrably what production runs.

**Recommendation.** Run `c2p-delivery-system/scripts/inspect_odoo_db.py --list`
and `--schema` per instance and commit the output to
`docs/project/INSTALLED_BASELINE.md`. This container cannot reach the VPS
(connection refused on 22 and 8069), so it must be run there. Half a day.

**Asked before.** This was raised in two earlier sessions and has not been
answered. It is the single highest-leverage unknown in the engagement.

---

## DEC-002 — One tenancy mechanism, not three **[OPEN] [BLOCKS PLT-01]**

**Question.** Which is authoritative: `mumtaz.tenant` (model), DB-per-tenant
(deployment), or `tenant_id` record rules filtering on
`user.partner_id.parent_id`?

All three exist in code simultaneously (1,093 lines of routing with 27 `sudo()`
calls between `portal_routing` and `subdomain_routing`, plus
`mumtaz_tenant_manager`'s 909 lines). Blueprint §4.3 requires tenant, legal
company, business unit, branch, department and project to be **distinct,
non-interchangeable** scopes. Three parallel mechanisms is how they stop being
distinct.

**Recommendation.** DB-per-tenant is the authoritative isolation boundary — it is
already deployed, it is the strongest boundary available, and `docs/ARCHITECTURE.md`
already documents it. Demote `mumtaz.tenant` to a *registry* record in the control
plane only, and delete the `tenant_id` record rules as redundant. Also add the
missing `branch_id` / `department_id` / `cost_centre` scopes, which no model has.

---

## DEC-003 — Does the Agency OS keep write access to client production? **[OPEN]**

**Question.** `c2p-delivery-system` can apply configuration and deploy code to
live Odoo databases over XML-RPC, gated by approvals in `delivery_api/policy.py`.
Should it retain that ability against **client production** databases?

**Recommendation. No.** Restrict the Agency OS to read + propose against client
production; let it write freely only to C2P-owned and staging databases. The
approval gate is well built, but a tool that can write to a client's ledger is a
tool that can end a client relationship, and the safer design costs almost
nothing. Blueprint §12 classes any ledger-affecting action as act-with-approval;
the stronger reading is that for *client* data it should be propose-only.

---

## DEC-004 — Is the CFO stack a subledger or a parallel ledger? **[OPEN] [BLOCKS FIN-01, Wave 2]**

**Question.** `mumtaz_cfo_base` / `_ingestion` / `_transactions` / `_toolkit`
hold 11 models and 969 lines beside standard `account`. Do they maintain balances
of their own?

- **Staging for ingestion** → correct, valuable, keep.
- **A subledger reconciled to control accounts** → acceptable, needs a
  reconciliation job and a posting catalogue.
- **A parallel ledger** → violates blueprint §4.2 (one authoritative owner per
  business fact) and must be unwound before any client data lands in it.

**Recommendation.** Read all four modules against the live schema and classify.
If it is a parallel ledger, stop new work on it immediately — the cost of unwinding
grows with every row.

---

## DEC-005 — Is inventory in scope? **[OPEN] [BLOCKS Wave 2 scope]**

**Question.** `mumtaz_marketplace`, `mumtaz_customer_portal` and
`mumtaz_vendor_portal` all depend on `stock`, but **0 of 978 fields** reference a
picking, a stock move or a valuation layer, and no module implements §6.3.

Either goods are in scope — and inventory-to-finance needs the full treatment
(valuation, landed cost, COGS/GRNI reconciliation) — or they are not, and three
`stock` dependencies should be removed.

**Recommendation.** For a consulting/services business, declare inventory **out of
scope** and drop the dependencies. Re-open only on a signed requirement from a
goods-trading client. A half-present inventory module is worse than none, because
it invites use without controls.

---

## DEC-006 — Signed authorisation matrix **[OPEN] [BLOCKS approval framework]**

**Question.** Who approves what, at which threshold? Discount above X%; write-off
above Y; fiscal lock date change; baseline reset; vendor-bill posting without a
receipt; cross-company recharge.

The TO-BE matrix in `SECURITY_MATRIX.md` §4 is a **proposal**. Blueprint §10.3 is
explicit that it must be adapted to a signed authorisation matrix, and §10.1
forbids silent self-approval — which cannot be enforced without knowing who the
approvers are.

**Recommendation.** One workshop, one signed table. Until then no approval code
should be written, because the thresholds *are* the specification.

---

## DEC-007 — Charter facts **[OPEN] [BLOCKS roadmap commitments]**

See `PROJECT_CHARTER.md`. Twelve profile fields are marked **To confirm** — legal
entities, tax jurisdictions, migration sources, user scale, go-live constraints.
A roadmap with dates on it before these are answered would be a guess dressed as
a plan, which blueprint §19 explicitly prohibits ("dependency-based, not calendar
promises").

**Recommendation.** Fill the charter before Wave 1 planning. It is a one-hour
conversation, not an investigation.

---

## DEC-008 — Merge the ERP rules into the root `CLAUDE.md`? **[OPEN]**

**Question.** The blueprint pack ships a `CLAUDE.md` "short execution contract"
(installed unmodified at `docs/erp-standard/ERP_CLAUDE_RULES.md`). The repository
root already has a `CLAUDE.md` holding hard-won operational knowledge — the
symlink gotcha, the `.env` location, the console's duplicate-function hazard.

Both are valuable and they do not conflict. The pack's own README says to place
its `CLAUDE.md` at the repo root, which would **overwrite** the existing one.

**Recommendation. Do not overwrite — merge.** Append a short "ERP engineering
contract" section to the root file pointing at
`docs/erp-standard/ERP_MASTER_BLUEPRINT.md` and
`docs/architecture/DEVELOPMENT_STANDARDS.md`, keeping the root file under the
blueprint's own 200-line guidance (§20). **Not done in this change** — it alters
the always-on instruction set for every future session, which is the owner's call,
not the architect's.

---

## Decided

*(none yet — this register starts at Wave 0)*
