# Project charter — DRAFT

**Status: DRAFT. Not signed. Not a scope commitment.**

Blueprint §2 forbids coding before these decisions, and §21 Step A forbids
substituting assumptions for signed scope. Fields marked **To confirm** are
genuinely unknown — they have been left blank rather than guessed, which is the
whole point of this document.

Owner to complete: Muhammad Umer, C2P Group.

---

## 1. Project profile

| Field | Value |
|---|---|
| Client / product name | **Two products.** (1) *Mumtaz* — multi-tenant SaaS ERP for GCC/Pakistan SMEs. (2) *C2P Agency OS* — internal AI-assisted Odoo delivery system. **[FACT]** from `docs/ARCHITECTURE.md` and `c2p-delivery-system/docs/00-vision.md` |
| Existing platform / version | Odoo **19 Community**. **[FACT]** — 38 manifests at `19.0.x`, no Enterprise dependency |
| Hosting | Hostinger VPS `187.77.128.199`, repo at `/opt/mumtaz`, five Odoo instances, nginx front, console at `delivery.mumtaz.digital`. **[FACT]** |
| Deploy path | `main` only; VPS pulls `main` via `c2p-delivery-system/deploy/update.sh`. **[FACT]** |
| Primary country / tax jurisdictions | **Partially known:** UAE (Peppol), KSA (ZATCA Phase 2), Pakistan (FBR) — inferred from `mumtaz_einvoicing` field names. **To confirm:** which are *contracted* vs aspirational, and which tax year opens first |
| Industry / verticals | 11 vertical playbooks exist in `c2p-delivery-system/delivery_api/data/industry_playbooks.json`. **To confirm:** which are live client commitments |
| Legal entities / branches / warehouses | **To confirm.** C2P Consultants and C2P Solutions are known to exist with a 60/40 split (`c2p_project_tracker`, `c2p-intercompany-reserve-close` skill). Branch and warehouse structure: **unknown — no branch model exists in code** |
| User roles and anticipated scale | 30 `res.groups` defined **[FACT]**. **To confirm:** user counts per role, tenant count target, transaction volume |
| Source systems / history to migrate | **To confirm — and this is urgent.** The live `Mumtaz_C2P` database already holds 41,182 CRM leads (29,484 archived by bulk action) **[FACT, prior session]**. Whether that is migration source, production data, or test residue determines whether it is protected or discarded |
| Required module scope | **To confirm.** See `02-CAPABILITY-MATRIX.md`: 8 capabilities are Missing and 2 need a scope decision (DEC-005) |
| Integrations / gateways | 11 present in code **[FACT]**, 0 registered per blueprint §13. **To confirm:** which are contractual |
| Environments and deploy approvals | dev → staging (`develop`, auto) → production (manual dispatch). **[FACT]** **To confirm:** who authorises a production deploy |
| Time / budget constraints | **To confirm** |
| Non-negotiable customizations / exclusions | **To confirm.** Known non-negotiable: Odoo **Community only** — no Enterprise dependency **[FACT]** |

## 2. Known fixed constraints **[FACT]**

1. **Odoo 19 Community.** No `web_gantt`, `project_enterprise`, `web_studio`,
   `documents` or `sign`. Verified across all 38 manifests.
2. **Deploys go to `main`.** Feature branches never reach production.
3. **`web/index.html` must be a symlink** to the console, never a copy — a copy
   goes stale silently.
4. **Service env file is `delivery_api/.env`**, not the repo root.
5. **Secrets never in git.** `.env`, `*.db`, `web/` gitignored; tokens encrypted
   at rest via `C2P_SECRET_KEY` (Fernet).
6. **Standard-first is the product's own stated discipline**, not an imposed one:
   standard config → native automation → Studio → custom-on-top (inherit, never
   recreate).
7. **PDFs must render on wkhtmltopdf 0.12.x** — no percentage bottom margins.
8. **60/40 commercial split**, configurable per project.
9. **Brand:** C2P charcoal `#0F0F0F` / red `#BE1E2D` / Arial / A4; Mumtaz ivory
   `#F5F3EF` / gold `#B8862A`.

## 3. Out of scope until signed

Blueprint §0: every capability must be marked Standard / Configure / Extend /
Integrate / Defer / Out of scope with an owner. Currently **unmarked**, therefore
out of scope by default: manufacturing, POS, e-commerce checkout, payroll,
helpdesk, field service, equipment/rental, inventory valuation (DEC-005),
consolidation and eliminations.

Listing them here is not a refusal — it is to stop them being assumed in.

## 4. Success criteria **[DESIGN — needs owner agreement]**

Blueprint §23 and §19 both forbid percentage-complete claims. Proposed criteria
are therefore **demonstrable transactions**, not progress bars:

1. The production security exposure is closed (`SEC-000`).
2. An installed-module baseline exists for all five instances (DEC-001).
3. CI installs every module into a throwaway database and runs its tests.
4. **One** business process is demonstrated end to end, with drill-down from a
   dashboard figure to the journal entries behind it.
5. Every figure on every client-facing dashboard and PDF reconciles to a posted
   record.
6. A role-and-company security test suite passes, including negative tests.

Criterion 4 is the real milestone. Everything before it is preparation and
everything after it is repetition.

## 5. What signing this charter changes

Until it is signed, the roadmap in `ROADMAP.md` carries **no dates** — only
dependency order. That is deliberate (blueprint §19: "dependency-based, not
calendar promises"). Signing the charter is what converts the sequence into a
schedule.
