# Mumtaz platform development roadmap

Written 21 Nov 2026 on branch `ccr-620c243b-p9qlq1` (base `main` at `ff1c797`).

This document sits above two existing plans and does not repeat them:

- the ERP programme: [`docs/erp/ROADMAP.md`](../erp/ROADMAP.md) (waves 0–5) and
  [`docs/erp/BACKLOG.md`](../erp/BACKLOG.md) (items #1–#20);
- the infrastructure audit:
  [`docs/infrastructure-audit/13_REMEDIATION_BACKLOG.md`](../infrastructure-audit/13_REMEDIATION_BACKLOG.md)
  (items V-, S-, B-, O-, A-) and its approval log in
  [`15_DECISIONS_AND_APPROVALS.md`](../infrastructure-audit/15_DECISIONS_AND_APPROVALS.md) §3.

Items from those plans are cited by ID. Decisions are cited by ID from
[`docs/erp/project/DECISION_REGISTER.md`](../erp/project/DECISION_REGISTER.md):
ADR-001…012, D-01…D-13 and the platform decisions P-01…P-17.

## 1. Conclusion

1. **The first working milestone exists and is tested.** An organization can
   register, choose Mumtaz ERP, be approved, receive a trial entitlement, get
   its own staging database, and its administrator can sign in. This runs end
   to end in `scripts/tenant_journey_ci.sh` against a real PostgreSQL and a
   real Odoo 19 server. It has run on a development rig only. It has not run on
   any Mumtaz server.
2. **Nothing may be enabled on a server yet.** No backup has been verified
   (audit B-02, B-03), application ports are reported open (S-03, S-04), and
   the control database is not identified (P-02). These gate every production
   step in this roadmap, whatever its phase.
3. **The next work that needs no owner input is governance and hardening in
   the repository:** registry checks that would have caught the defects found
   in the existing bundles (PL-01), tenant lifecycle (PL-03), delivery of the
   set-password link (PL-04), and the ZAKI connector fix (PL-12, first step).
4. **Seventeen platform decisions are open (P-01…P-17).** Six of them block
   most of the remaining work: P-01 (one tenancy model), P-02 (which database
   is the control plane), P-03 (where provisioning is switched on first),
   P-05 (single sign-on), P-09 (one price list), P-17 (per-tenant database
   role and backups).
5. **This is consolidation, not a rebuild.** The control plane is the existing
   `mumtaz_tenant_manager` and `mumtaz_control_plane` modules. No second
   control plane is started.

## 2. Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at the cited path, or produced by the named command on 21 Nov 2026. |
| **REPORTED** | Stated in a repository document or an earlier audit; not re-checked here. |
| **PROPOSED** | A plan or design. Not built. |
| **UNKNOWN** | Needs server evidence or an owner decision. |

Sizes are relative: **S** (one focused change), **M** (several changes and
their tests), **L** (a multi-part piece of work). No dates are given. Order
comes from dependencies.

## 3. Slice 1 — done in this branch (VERIFIED)

The journey: **Register organization → Choose Mumtaz ERP → Assign entitlement →
Provision isolated staging tenant → Open ERP workspace.**

| Part | What exists now | Evidence |
|---|---|---|
| Registration request | `mumtaz.signup.request` in `mumtaz_control_plane`: new → approved → provisioning → ready / failed / rejected | `addons/mumtaz_control_plane/models/signup_request.py`; `tests/test_signup_journey.py` |
| Product catalogue | `mumtaz.product` with a status set from evidence. Only Mumtaz ERP is open to requests; ZAKI, Marketplace, Delivery OS and Pharma are "planned" | `data/product_catalogue.xml`; test `test_catalogue_is_honest` |
| Approval | A Super Admin approves. That creates the organization (`res.partner`), a **staging** tenant record whose database name starts with `stg_`, and a trial subscription. No database is created at this step | test `test_approval_creates_organization_staging_tenant_and_entitlement` |
| Entitlement gate | Provisioning is refused unless the existing feature-access service grants the product's access feature | tests `test_no_provisioning_without_entitlement`, `test_plan_without_the_access_feature_cannot_be_approved` |
| Real provisioning | The existing `RealProvisioner`, now with a verification step (every module installed, administrator login set), a one-time set-password link from Odoo's own invitation token, and no dependence on the database manager being exposed | `addons/mumtaz_tenant_manager/services/provisioning.py`; `scripts/tenant_journey_ci.sh` |
| Dry run cannot activate | A simulated run leaves the tenant in draft. Before this change a dry run marked the tenant active, and the wizard's "Dry Run" box was ignored | tests `test_dry_run_never_activates`, `test_queue_without_real_provisioning_does_not_activate`, `test_dry_run_does_not_make_the_request_ready` |
| Permission | Only a Platform Administrator can queue provisioning; the Platform Manager group can edit a tenant but not provision it | tests `test_platform_manager_cannot_provision`, `test_only_super_admin_approves_and_provisions` |
| Install profile | Bundle `mumtaz_erp`: base, mail, contacts, crm, sale_management, purchase, stock, account, mumtaz_financial_reports. No control-plane module, no `mumtaz_sso` | `addons/mumtaz_tenant_manager/data/mumtaz_bundle_data.xml`; test `test_erp_profile_modules_exist_and_stay_out_of_the_control_plane` |
| Public intake | `POST /mumtaz/cp/signup`, closed by default. It can only create a pending request | `controllers/signup.py`; tests `TestSignupRoute`, `test_public_intake_*` |
| Unit tests | 30 tests in the two modules, 0 failed, on a fresh Odoo 19 database | `odoo-bin -i mumtaz_tenant_manager,mumtaz_control_plane --test-enable` |
| End to end | Real database created, isolation read from PostgreSQL, HTTP sign-in through the one-time link | `scripts/tenant_journey_ci.sh`, added as a step of `.github/workflows/platform-odoo-install.yml` |

What Slice 1 does **not** do: it does not send the link by email, expire a
trial, bill anyone, install a localisation, give the tenant its entitlements
at run time, or provide single sign-on. Those are PL-03 to PL-11 below. The
result of the first CI run of the new workflow step is UNKNOWN until the pull
request runs.

## 4. Phases 0–8

| Phase | Goal | Already done (evidence) | Exit criteria | Blocking decisions | Depends on |
|---|---|---|---|---|---|
| **0 Audit** | A verified picture of what exists | Repository and code audit, 16 documents (VERIFIED: `docs/infrastructure-audit/`). ERP audit and capability matrix (VERIFIED: `docs/erp/00-AUDIT.md`, `01-CAPABILITY_MATRIX.md`). Module, ZAKI and website reviews (VERIFIED: `docs/platform/`). **Server facts are still REPORTED only** | The read-only verification pack V-01…V-12 has been run and its output recorded; each database has its installed-module list on file | Audit D-02, D-03 | — |
| **1 Architecture and governance** | One architecture, one module registry, one decision record | Six-layer registry with a CI check (VERIFIED: `scripts/module_registry.py --check`). `sudo()` labelling in CI (VERIFIED: `scripts/check_sudo.py`). Proposed owners, profiles and 13 new checks (PROPOSED: `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §8) | Registry carries owner and install profiles; CI fails on an unknown module name in a bundle and on a control-plane module in a tenant profile (PL-01); P-01 and P-16 answered | P-01, P-15, P-16 | Phase 0 for the `installed_in` field only |
| **2 SaaS control plane** | One control plane that registers, entitles, provisions, bills and retires tenants | Slice 1 (section 3). Plans, features, subscriptions, lifecycle crons and a Stripe module exist but are untested (VERIFIED: registry shows 0 test files for `mumtaz_billing_stripe`) | The journey passes on the target server's staging; trial expiry suspends a tenant; the link reaches the administrator by email; registration is protected before it is opened; a named person has approved the enablement | P-02, P-03, P-04, P-05, P-07, P-08, P-09, P-17 | Audit batches 2A–2E before any server step |
| **3 ERP commercial readiness** | A general ERP tenant that a paying customer can run its books on | ERP waves and backlog (VERIFIED as a plan: `docs/erp/ROADMAP.md`, `BACKLOG.md`); backlog #1, #2, #3 built (REPORTED in `RELEASE_CHANGELOG.md`) | ERP backlog #5, #8, #9, #10, #11 accepted; ERP roadmap waves 1–2 exit evidence | ADR-005, ADR-006, D-02, D-06, P-06 | Phase 2 for provisioning; ERP wave gates |
| **4 Website and unified UX** | The public site on native Odoo Website, one design system | `mumtaz_website_builder` with ten blocks and seven tests (VERIFIED at `ff1c797`, see `MUMTAZ_WEBSITE_IMPLEMENTATION.md` §4.1). Proposed token set (PROPOSED: `MUMTAZ_DESIGN_SYSTEM.md` §3) | Gaps in `MUMTAZ_WEBSITE_IMPLEMENTATION.md` §4.3–4.4 closed; runs on its own instance; owner signs off on the staging URL; the live homepage is replaced only on a named approval | D-09, D-11, D-13, P-09, P-10, P-14 | Phase 2 only for the "start a trial" link |
| **5 Product integration** | Jawhar, Pharma, ZAKI and Delivery OS reachable through the same control plane | Jawhar: 15 modules with their own suite (VERIFIED: `scripts/jewel_ci.sh`). ZAKI: canonical architecture proposed, no safe implementation (VERIFIED: `MUMTAZ_AI_ARCHITECTURE.md` §4). Pharma: not on `main` (REPORTED). Delivery OS: FastAPI, internal use (VERIFIED in code) | A Jawhar tenant is provisioned by the journey script from a `jawhar` profile; ZAKI slice 1 passes its tests; each product's catalogue status is changed only with recorded evidence | P-05, P-11, P-13, D-03, D-10 | PL-07 (tenant-side agent); Phase 2 |
| **6 Marketplace MVP** | Opt-in supplier discovery, catalogues, requests for quotation | `mumtaz_marketplace` exists but assumes tenants share a database (VERIFIED: `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §7.2) | Topology decided; one tenant can publish a catalogue and another can send a request for quotation without either reading the other's database | P-12 | PL-07; Phase 2 |
| **7 White-label and institutional** | A partner's brand on a tenant; partner-owned tenants | `mumtaz.brand` record exists and nothing renders it (VERIFIED: `MUMTAZ_DESIGN_SYSTEM.md` §4.1). Specification for Jawhar (REPORTED: `docs/jawhar/WHITE_LABEL_SPECIFICATION.md`) | A tenant resolves host → tenant → brand → tokens; contrast rule enforced; partner cannot see another partner's tenants | P-14, D-13 | Phases 2 and 4 |
| **8 Product expansion** | Further editions and services on the same rails | Nothing | Each new product enters the catalogue as "planned" and moves up only with evidence | Case by case | Phases 2, 5 |

## 5. Backlog of the next slices

Ordered by value, then dependency, then risk. "Safe now" means it can be built
and tested in the repository without an owner decision and without touching a
server.

| ID | Slice | Why | Depends on | Blocked by | Acceptance (GIVEN / WHEN / THEN) | Size | Safe now? |
|---|---|---|---|---|---|---|---|
| **PL-00** | **Server prerequisites** — audit batches 2A–2E: verification pack (V-01…V-12), first off-host backup and a restore test (B-01…B-03), ports closed (S-03, S-04, S-05), one database per process (S-06), database manager denied (S-09) | Every production enablement below is unsafe without it | — | Audit D-02, D-03, D-05; owner runs it | GIVEN the VPS WHEN the V-pack runs THEN its output is on file; GIVEN a production dump WHEN restored on another machine THEN Odoo starts and row counts match | L | No — owner and server |
| **PL-01** | **Registry schema and profile checks in CI** — add `owner` and `profiles` to `registry/classification.json`; checks 1–6 of `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §8.4 | The existing bundles name an Enterprise-only module and pull the tenant registry into customer databases; nothing catches either | — | P-16 for the final schema (the checks can start as a ratchet with known exceptions listed) | GIVEN a bundle naming a module absent from Odoo 19 Community and from `addons/` WHEN `module_registry.py --check` runs THEN it fails and names the bundle. GIVEN a tenant profile whose dependency closure contains `mumtaz_tenant_manager` THEN it fails | M | Yes |
| **PL-02** | **Fix the five older bundles** — drop `account_accountant`; use `sale_management`; remove `mumtaz_sme_profile`, `mumtaz_onboarding`, `mumtaz_voice` from tenant bundles until decoupled | Customer databases must not hold the tenant registry or the price list | PL-01 | P-06 (content), P-09 (prices). The data file is `noupdate`: an existing control database needs a manual edit, which needs approval | GIVEN a fresh control database WHEN each bundle is provisioned by the journey script THEN no control-plane table exists in the tenant database and no module is skipped silently | S | Repository part yes; existing databases no |
| **PL-03** | **Tenant lifecycle** — trial expiry → suspended → archived; a suspended tenant stops routing; reactivation; **no automatic database deletion** | Slice 1 creates tenants and nothing ever ends them | Slice 1 | P-07 for durations and whether staging tenants are neutralised | GIVEN a trial past its end date WHEN the lifecycle cron runs THEN the subscription is expired, the tenant is suspended and the database still exists. GIVEN an archived tenant THEN its database is listed for a person to remove and is not dropped by code | M | Yes (durations as settings) |
| **PL-04** | **Deliver the set-password link** — email it to the administrator from the control database; resend on request; show its expiry; never log it | Today an operator copies the link by hand | Slice 1 | P-02 (which instance sends mail) for production; none for the code | GIVEN a provisioned tenant WHEN provisioning ends THEN one email with the link is queued for the administrator's address and the link appears in no log file. GIVEN a used link WHEN "resend" is pressed THEN a new link is issued and the old one stays dead | S | Yes |
| **PL-05** | **Protect public registration** — email verification before a request reaches the review queue; captcha; per-address throttle at the proxy (S-10) | The route is closed by default and must stay closed until this exists | Slice 1 | P-08 | GIVEN the route is open WHEN an unverified address submits THEN no request is visible to reviewers until the address is confirmed. GIVEN a burst from one address THEN it is refused before reaching Odoo | M | Code yes; opening it no |
| **PL-06** | **Localisation by country in the ERP profile** — ERP backlog #5 | A new tenant has no chart of accounts or taxes | PL-01 | ADR-006, D-06, P-06 | As ERP backlog #5; in addition the journey script provisions a UAE tenant and finds a chart, VAT taxes and no tax rate in the repository | M | No — needs the finance decisions |
| **PL-07** | **Tenant-side agent** — a small module with no dependency on the control plane: holds the tenant code and a per-tenant token, reads its entitlements from the control plane, reports usage | The feature-access service resolves `mumtaz.tenant` locally, so a tenant database cannot ask what it is entitled to. Prerequisite for Jawhar, ZAKI and Marketplace under the control plane | Slice 1, PL-01 | P-02, P-05 (the token design is shared with single sign-on) | GIVEN two tenants WHEN tenant A's agent asks for entitlements with its token THEN it receives A's only; with B's code and A's token it is refused. GIVEN the control plane is unreachable THEN paid features fail closed after a stated grace period | L | Design yes; build after P-05 |
| **PL-08** | **Decouple control-plane modules from tenant modules** — cut `mumtaz_tenant_manager` / `mumtaz_control_plane` out of the dependencies of `mumtaz_cfo_base`, `mumtaz_marketplace`, `mumtaz_voice`, `mumtaz_onboarding`, `mumtaz_sme_profile` | `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §5.6 | PL-07, PL-01 | P-01; inventory of where each module is installed (PL-00) | GIVEN each of those modules WHEN installed alone on a fresh database THEN `mumtaz_tenant` does not exist there; `platform_ci.sh` stays green | L | No — needs the inventory |
| **PL-09** | **Single sign-on redesign** — replace the shared secret (audit A-09) with a per-tenant or asymmetric credential, host binding, nonce and a short lifetime | One secret across tenants allows cross-tenant sign-in (audit ODOO-01). `mumtaz_sso` is excluded from the new profile until this is done | PL-07 | P-05 | GIVEN a token minted for tenant A WHEN presented to tenant B THEN refused. GIVEN a used token THEN refused. GIVEN an expired token THEN refused | M | No — needs P-05 |
| **PL-10** | **Billing connection** — tests for `mumtaz_billing_stripe` (webhook retries, amount checks, idempotency); trial → paid conversion | The module exists with 0 tests; audit A-11 and A-12 list defects | PL-03 | P-09; a Stripe test account | GIVEN a webhook delivered twice WHEN processed THEN one billing record. GIVEN an amount that does not match the plan THEN refused and logged. No live key in the repository | M | Tests against recorded fixtures yes; live connection no |
| **PL-11** | **Jawhar install profile and bridge** — a `jawhar` bundle; a thin `mumtaz_jewellery_platform` module on top of PL-07 | The catalogue lists Jawhar as a pilot with no way to provision it | PL-07, PL-01 | P-05; Jawhar rules in `docs/mumtaz-jewel/CLAUDE.md` | GIVEN the catalogue WHEN a Jawhar request is approved and provisioned THEN the 13 Jawhar modules are installed, the demo and website modules are not, and `jewel_ci.sh` stays green | M | Bundle yes; bridge after PL-07 |
| **PL-12** | **ZAKI slice 1** — as `MUMTAZ_AI_ARCHITECTURE.md` §6: fix `zaki_connector`, extract the AI core from Jawhar, add `/zaki/api/ask` at levels A and B | No ZAKI implementation is safe to expose; briefings show cash 0 | Step 1 has no dependency; metering needs PL-07 | P-11, D-03 for steps 2–3 | As the acceptance tests in `MUMTAZ_AI_ARCHITECTURE.md` §6 | L | Step 1 yes; steps 2–3 after P-11 |
| **PL-13** | **Website gaps** — tokens instead of hex literals, focus states, self-hosted fonts, RTL, SEO meta, privacy page, removal of prices and claims that no decision backs | `MUMTAZ_WEBSITE_IMPLEMENTATION.md` §4.2–4.4 | PL-15 for tokens | D-11, P-09 for prices; P-14 for tokens | GIVEN the page WHEN rendered in Arabic THEN layout mirrors and no heading has negative letter-spacing; an automated accessibility check reports no contrast or focus failure; no price appears that is not in the one price source | M | Structural fixes yes; content no |
| **PL-14** | **Dedicated website instance** — `MUMTAZ_WEBSITE_IMPLEMENTATION.md` §5–6 | The module's global side effects must not land on an ERP or client database | PL-13, PL-00 | D-09, P-10; named approval for each cut-over step | As the cut-over plan and rollback in that document §6 | M | No — server |
| **PL-15** | **Design tokens** — one `--mz-*` token file; website first, then `mumtaz_theme`, then the apps | Several competing palettes; gold-first in most sources | — | P-14, D-13 | GIVEN the token file WHEN a partner brand overrides primary and accent THEN contrast ≥ 4.5:1 is checked and a failing pair is refused | M | Draft yes; adoption after P-14 |
| **PL-16** | **Retire company-per-organization tenancy** — map `mumtaz.org` rows to `mumtaz.tenant`, then retire `mumtaz_org_config` | Two tenancy models contradict ADR-002 | PL-00 (row counts), PL-08 | P-01 | GIVEN a copy of the database holding `mumtaz.org` rows WHEN the migration runs THEN every row has a tenant record, counts match, and no company created by signup is deleted | M–L | No — needs P-01 and the counts |
| **PL-17** | **Customer-specific data out of reusable code** — the client brand in `mumtaz_ceo_dashboard`, the database name in a seed script, staff addresses and project ids in a hook, the knowledge block in `c2p_master_agent` | `MUMTAZ_MODULE_REGISTRY_REVIEW.md` §9 action 2; the repository is public | — | P-15 for where the data goes | GIVEN the repository WHEN the hardcoding lint (check 9) runs for non-customer owners THEN no client name, staff address or database name is found outside an allow-list with reasons | M | Lint yes; moving data after P-15 |
| **PL-18** | **Per-tenant database role and tenant backups** | REPORTED: one shared PostgreSQL role serves every database, so isolation today is by database name only | PL-00 | P-17 | GIVEN tenant A's role WHEN it connects to tenant B's database THEN refused. GIVEN a new tenant THEN it is in the nightly backup and one restore has been tested before it is called paid | M | No — server |
| **PL-19** | **Enable real provisioning on the first server, staging only** | Moves Slice 1 from a rig to the real platform | PL-00, PL-03, PL-04, PL-18 | P-02, P-03; named approval in the approval log | GIVEN the target server's staging WHEN `tenant_journey_ci.sh` runs there THEN it passes; a rollback (switch off the flag, list the databases created) is written and rehearsed | S | No — approval and server |
| **PL-20** | **Marketplace topology and MVP** | Phase 6 | PL-07 | P-12 | See phase 6 exit criteria | L | No |
| **PL-21** | **Delivery OS as a subscribable service** — evaluation first; the FastAPI foundation stays | Phase 5 | Audit A-03…A-08 | P-13 | GIVEN the evaluation THEN a written recommendation exists before any code moves | M (evaluation) | Evaluation yes |

## 6. What can start, and what cannot

### 6.1 Safe to do now, without owner input

- PL-01 registry checks as a ratchet (known exceptions listed, like `known_violations`).
- PL-02 repository part: correct the bundle data file for new installs.
- PL-03 tenant lifecycle with durations as settings.
- PL-04 emailing and resending the set-password link.
- PL-05 code for verification and captcha hooks, with the route left closed.
- PL-10 Stripe tests against recorded fixtures.
- PL-11 `jawhar` bundle definition (not the bridge).
- PL-12 step 1: the `zaki_connector` fix and its tests.
- PL-13 structural website fixes: tokens, focus, RTL rules, fonts.
- PL-17 the hardcoding lint with an allow-list.
- ERP backlog items that are not marked ⚠ (#8, #9, #13).

### 6.2 Needs a decision first

| Decision | Unblocks |
|---|---|
| P-01 one tenancy model | PL-08, PL-16 |
| P-02 which database is the control plane | PL-04 (production), PL-07, PL-19 |
| P-03 where provisioning is enabled first | PL-19 |
| P-05 single sign-on design | PL-07, PL-09, PL-11 |
| P-06 ERP profile content and localisation; ADR-006; D-06 | PL-02, PL-06 |
| P-07 trial and staging lifecycle | PL-03 (final values) |
| P-08 opening public registration | PL-05 (opening it) |
| P-09 one price list; D-11 | PL-02 (prices), PL-10, PL-13 |
| P-10 website host; D-09 | PL-14 |
| P-11 canonical ZAKI; D-03, D-10 | PL-12 steps 2–3 |
| P-12 marketplace topology | PL-20 |
| P-13 Delivery OS as a service | PL-21 beyond evaluation |
| P-14 design tokens; D-13 | PL-13, PL-15 |
| P-15 where customer-specific data goes | PL-17 |
| P-16 registry schema | PL-01 (final form) |
| P-17 per-tenant role and backups | PL-18, and with it any paying tenant |

### 6.3 Needs server access (the owner runs it, or grants read-only access)

- PL-00: V-pack, first backup, restore test, firewall. Audit batches 2A–2E.
- The installed-module list per database (V-11), which decides PL-08 and PL-16.
- Which copy of the website and of ZAKI is live (V-03, V-06).
- PL-14, PL-18, PL-19.
- Whether `list_db` is off and the database manager is denied (S-09).

## 7. Non-goals

- **No second control plane.** The existing modules are completed, not replaced.
- **No rewrite of Delivery OS.** Its FastAPI foundation stays until it has been evaluated (PL-21).
- **No renaming of installed modules.** A rename happens only with a migration
  and an inventory of every database where the module is installed.
- **No change to IG2 or Faizy.** IG2 is a client's system: nothing is applied
  to it without a compatibility test and approval. Faizy stays independent on
  its own branch.
- **No production change without a named approval** recorded in the approval log.
- **No merging of the C2P and IG2 databases, no deletion of any database, no
  destructive migration** without explicit authorization.
- **No product is called available because a screen looks right.** Catalogue
  status moves only with recorded evidence.

## 8. How this roadmap is kept current

- A slice is marked done here only when its tests pass and the command and
  result are recorded in [`docs/erp/quality/RELEASE_CHANGELOG.md`](../erp/quality/RELEASE_CHANGELOG.md).
- Acceptance tests for each PL item are in
  [`MUMTAZ_TEST_AND_ACCEPTANCE_PLAN.md`](MUMTAZ_TEST_AND_ACCEPTANCE_PLAN.md).
- A decision that is answered is recorded in the decision register, and the
  "blocked by" column here is updated in the same change.
