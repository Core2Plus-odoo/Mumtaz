# Decision register

Statuses: **Decided** (made by the owner, with its source) · **Proposed** (my recommendation, awaiting the owner) · **Open** (a fact only the business can supply). Nothing marked Proposed or Open may be treated as approved ("Unknown is not equivalent to approved", blueprint §2). Template for each architecture decision: [`../templates/ADR_TEMPLATE.md`](../templates/ADR_TEMPLATE.md); each row below becomes one ADR file when it is decided.

## A. Architecture decisions (blueprint ADR-001..012)

| ADR | Decision | Evidence / options | Recommendation | Status | Owner |
| --- | --- | --- | --- | --- | --- |
| ADR-001 | Odoo extension vs custom ERP vs integration | `[V]` 63 Odoo 19 add-ons, `FROM odoo:19`, tenant provisioning by cloning an Odoo DB | **Odoo 19 Community extension add-ons** (ERP-connected apps only for AI/portal, ERP stays the system of record) | Proposed (de facto in force) | Owner |
| ADR-002 | Tenant model | `[V]` `docs/ARCHITECTURE.md` §2: one DB per tenant; pharma `mumtaz_pharma` with `dbfilter ^mumtaz_%d$` | **Database per tenant**; company scope inside a tenant is separate (ADR-003) | Proposed (documented, in force) | Owner |
| ADR-003 | Company, branch, department, warehouse model | `[V]` pharma has no `company_id`; options: (a) single legal entity per pharma DB, enforce and test it; (b) full multi-company with record rules | **Open**: needs entity count. Until decided: (a) by default, documented | **Open** → D-003 | Controller |
| ADR-004 | Financial source of truth | `[V]` Odoo `account` + third-party kit (pinned `fdeea97d`), hardened; options: kit; build minimum; Enterprise | **Odoo `account` as ledger of record; kit accepted with the hardening module and a review at every minor upgrade** | Proposed | Controller |
| ADR-005 | Inventory valuation | standard / average / FIFO; negative stock policy; pharma lot and expiry | Decide with the accountant; pharma likely lot-tracked FEFO | **Open** → D-005 | Accountant |
| ADR-006 | Localization | `[V]` generic COA on staging, no `l10n_pk`; options: official localization, custom chart, generic | Choose a Pakistan chart and tax mapping reviewed by a local accountant; **no statutory rule hard-coded** | **Open** → D-006 | Accountant |
| ADR-007 | Approval engine | Community has no approvals app; per-model maker-checker exists | One generic approval mixin (bands, delegation, log) | Proposed → D-007 | Controller |
| ADR-008 | Integration strategy | `[V]` idempotent raw-event ingestion; platform XML-RPC | Contract per integration (pack template), idempotency keys, DLQ view, no direct DB access | Proposed → D-008 | Tech lead |
| ADR-009 | Security and identity | RBAC groups; platform JWT SSO; MFA unknown | RBAC + Auditor role + record rules; SSO/MFA for privileged roles | **Open** → D-009 | Tech lead |
| ADR-010 | Deployment and DR | single VPS; dumps before each change; RPO/RTO undefined | Define RPO/RTO, off-site backup, restore drill | **Open** → D-010 | Owner |
| ADR-011 | Close and correction policy | lock dates not configured; reversal built (draft) | Lock dates per period; reversals only; backdating needs a controller | **Open** → D-011 | Accountant |
| ADR-012 | Odoo version and dependency policy | `[V]` 19.0 (build 20260719); kit pinned; Python deps isolated | Pin and test per minor build; dependency scan in CI | Proposed | Tech lead |

## B. Gate-0 decisions the business must make

| ID | Question | Why it matters | Default until answered |
| --- | --- | --- | --- |
| D-001 | What is "the ERP"? One per tenant/vertical (pharma first), not the whole repository | The repo holds five products; one directive cannot cover them equally | Pharma is the reference ERP; platform and jewellery tracked separately |
| D-002 | Module scope for the pharma tenant: HR/payroll, manufacturing, projects, service, POS, subscriptions in or out | Drives the matrix dispositions | **Out (Defer)** until signed |
| D-003 | How many legal entities, branches, currencies does the pharma tenant have | Company scope, record rules, Monetary migration | One entity, one currency, enforced by a test |
| D-004 | Install the pack's `CLAUDE.md` into the repository? The repo already has a root `CLAUDE.md` (Mumtaz working knowledge) | Overwriting would lose it | **Do not overwrite.** Proposed: append a short pointer to `docs/erp/` and the pack's execution protocol; owner approves the text |
| D-005 | Inventory costing and valuation policy | stock entries, COGS, GRNI | none; blocks P2P/inventory slices |
| D-006 | Pakistan localization: chart, taxes, e-invoicing, withholding treatment, payroll | statutory correctness | none; blocks real accounting |
| D-007 | Approval bands and delegation | who approves what, up to what amount | none |
| D-008 | Integration ownership: courier files vs API, bank feeds, channels | contracts and credentials | files only (as built) |
| D-009 | Identity: SSO, MFA, who administers roles | segregation of duties | RBAC only |
| D-010 | RPO/RTO, backup retention, off-site, restore drill owner | continuity | dumps before changes only |
| D-011 | Period close, lock dates, backdating authority | R2R integrity | none configured |
| D-012 | Accept this audit, matrix, standards, roadmap and backlog (or amend) | starts G0/G1 sign-off | pending |

## C. Decisions already made in this engagement (owner instructions)

| ID | Decision | Source |
| --- | --- | --- |
| DEC-01 | Pharma tenant is **staging only**; never touch `main`, other tenants' databases or production services; ask before nginx, DNS, certbot, restarts other than `odoo-pharma`, installs/upgrades on `mumtaz_pharma` | original task |
| DEC-02 | Names are generic (no client, courier, product or partner names) in code, data and docs | original task |
| DEC-03 | No credential is ever printed, recorded or committed | original task |
| DEC-04 | Every ERP-writing action is **draft-only**; accountants post | built as stated; owner did not object (treat as **Assumed**) |
| DEC-05 | One app per business area, not one big menu | owner request 2026-11-20 |
| DEC-06 | Strict process order with a logged override; advisory mode switchable | proposed by me, owner proceeded (treat as **Assumed**) |
| DEC-07 | Scope of slice 1: Pakistan COD with statement upload, extending the reconciliation hub | owner: "pakistan specific, go" |
| DEC-08 | Evidence rule: a gate counts only with pasted output; the owner runs VPS gates | followed throughout; adopted as standard |
