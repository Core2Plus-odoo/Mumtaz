# Mumtaz SaaS control plane

**Conclusion.** A control plane already exists in this repository as Odoo
modules (`mumtaz_tenant_manager`, `mumtaz_control_plane`,
`mumtaz_billing_stripe`). It is the one to complete; nothing here justifies a
second one. Until 21 Nov 2026 it could not carry a customer from registration
to a working workspace, and it could report success without creating anything.
Slice 1 (this branch) closes that gap for one product, Mumtaz ERP, in staging
only, and proves it with a real database on a development rig. It has **not**
been run on any server.

Status words used below:
**VERIFIED** — read in code or run on a local Odoo 19 + PostgreSQL 16 rig on 21 Nov 2026 ·
**REPORTED** — from a repository document or an earlier note, not re-checked (everything about the live server is in this class) ·
**PROPOSED** — designed, not built ·
**UNKNOWN** — needs server evidence or an owner answer.

> **Correction, 22 Nov 2026 (server evidence).** The conclusion above was
> drawn from `main`. The server shows more: nginx serves a control-panel
> front end from `/opt/mumtaz/platform/frontend`, and the production branch
> `claude/resume-help-95ne9v` carries `platform/control-panel/`, an
> 800-line FastAPI service with sign-up, tenants, Odoo provisioning, a
> sign-on link, impersonation and billing. It was deleted from `main` in
> PR #124. So there may be **two** control planes: that service (possibly
> running, on an unmerged branch, with no tests) and the Odoo modules
> described here (on `main`, tested, never run on the server). Which one is
> kept is decision P-02; until the server check says whether the FastAPI
> service is running and holds real tenants, do not retire either. Details:
> `MUMTAZ_DEPLOYMENT_REGISTRY.md` §0.

## 1. What `app.mumtaz.digital` is today

| Item | State |
| --- | --- |
| The site served at `app.mumtaz.digital` | SERVER (22 Nov 2026): nginx has a root at `/opt/mumtaz/platform/frontend`, the control-panel front end of the `platform/` rebuild — not the static portal in `sites/app.mumtaz.digital/portal`. Whether its back end (port 8002) is running is UNKNOWN |
| The control-plane code | VERIFIED: Odoo modules in `addons/`, listed in §2 |
| Which Odoo database holds the control plane | UNKNOWN (decision P-02). No document names one |
| Whether any tenant was ever provisioned through `mumtaz.tenant` | UNKNOWN |
| The stalled rebuild in `platform/` | VERIFIED in code: a schema and a ZAKI backend, with the control panel it depends on absent. Not continued |

## 2. What exists, module by module (VERIFIED)

| Capability the directive asks for | Where it is | State before slice 1 | After slice 1 |
| --- | --- | --- | --- |
| Tenant registry | `mumtaz_tenant_manager` — `mumtaz.tenant` | Works. No notion of staging vs production | `environment` field; staging databases must be named `stg_…` |
| Install profiles | `mumtaz.module.bundle` + `data/mumtaz_bundle_data.xml` | Five bundles; none is a general ERP; three name an Enterprise-only module that is skipped silently; four pull the tenant registry into the customer database | New profile `mumtaz_erp` (standard CRM, sales, purchasing, inventory, accounting + financial reports). The five old bundles are unchanged (see §7) |
| Provisioning | `services/provisioning.py`, wizard, 5-minute scheduled worker | Real provisioner worked only with the database manager exposed; ignored initialisation failures; **a dry run marked the tenant active**; the wizard's "Dry Run" box was never read | Only a real, verified run activates. Works with the database manager hidden. The box is honoured both ways |
| Product selection | — | None. Plans had no product | `mumtaz.product` catalogue with an evidence-based status; plans belong to a product |
| Organization registration | `mumtaz_org_config` (`mumtaz.org`, company-per-org in one database) and `mumtaz_organization` (`mumtaz.sme.signup`, a partner directory) | Neither leads to a tenant database | `mumtaz.signup.request` in the control plane; the organization of record is a standard `res.partner` |
| Subscriptions | `mumtaz_control_plane` — `mumtaz.subscription`, lifecycle policies, crons | Models and screens exist; no plan was seeded | One plan seeded: "Mumtaz ERP — staging trial" |
| Entitlements | `mumtaz.feature`, `mumtaz.plan.feature`, `mumtaz.tenant.feature`, `mumtaz.feature.access.service` | Resolver works; nothing gated provisioning on it | Provisioning is refused without the product's access feature |
| Users and identity | Odoo users per database; `mumtaz_sso` (HMAC link) | SSO uses one secret shared by every tenant (audit ODOO-01, critical) | SSO is in no profile. First access is Odoo's own one-time invitation link |
| Billing | `mumtaz_billing_stripe` | Present, 0 tests, never exercised here | Untouched. Not connected to the journey |
| Routing by subdomain | `mumtaz_subdomain_routing` | Present, off unless `MUMTAZ_DBFILTER_ROUTING=1` | Untouched |
| White-label | `mumtaz.brand`, `tenant.partner_id` | A record nothing renders | Untouched |
| Workspace | `tenant.workspace_url` | — | Computed from subdomain or custom domain |

## 3. The journey that now works (VERIFIED)

```
Register organization      POST /mumtaz/cp/signup  (closed by default)  or an operator enters it
        │                  → mumtaz.signup.request, state "new". Nothing else is created.
Choose Mumtaz ERP          product_id = erp, plan_id = erp_staging_trial
        │
Approve (a person)         → res.partner (organization + contact)
        │                  → mumtaz.tenant: environment staging, database stg_<code>, state draft
Assign entitlement         → mumtaz.subscription: trial, 14 days
        │                    the resolver must grant the product's access feature, or approval rolls back
Provision (a person)       refused without entitlement → tenant queued
        │
Scheduled worker           creates the database, installs the profile, verifies it,
        │                  issues the administrator's one-time set-password link
Open ERP workspace         the administrator opens the link, chooses a password, lands in /odoo
```

States: request `new → approved → provisioning → ready` (or `failed`,
`rejected`); tenant `draft → provisioning → active`.

What makes the result trustworthy:

| Rule | Where it is enforced | Test |
| --- | --- | --- |
| A tenant becomes `active` only after a real run that passed verification | `mumtaz.tenant._apply_provision_result` — the single place | `test_dry_run_never_activates`, `test_queue_without_real_provisioning_does_not_activate`, `test_dry_run_does_not_make_the_request_ready` |
| A dry run creates nothing even on a server allowed to create databases | `get_provisioner(dry_run=True)` | `test_provisioner_choice`, `test_dry_run_never_activates` |
| A real run is refused, with no state change, on a server not allowed to create databases | `ProvisioningDisabled` → `UserError` in the wizard | `test_real_run_refused_when_server_disallows_it` |
| No entitlement, no provisioning | `mumtaz.signup.request.action_provision` | `test_no_provisioning_without_entitlement` |
| A plan that does not grant the product cannot be approved | `action_approve` (rolls back) | `test_plan_without_the_access_feature_cannot_be_approved` |
| Only platform administrators create databases | `_check_can_provision`, `_check_can_decide` | `test_platform_manager_cannot_provision`, `test_only_super_admin_approves_and_provisions` |
| Verification after the run: every module of the profile installed, administrator present with the right login | `RealProvisioner._verify` | end-to-end script |
| A failed run never drops a database; it flags the leftover for a person | `database_needs_cleanup`, `action_provision` refuses a blind retry | `test_failure_leaves_draft_and_flags_the_leftover_database`, `test_failed_run_blocks_a_blind_retry` |
| The customer database holds no control-plane tables | profile content + closure test | `test_erp_profile_modules_exist_and_stay_out_of_the_control_plane`; end-to-end isolation checks |
| No password is stored or sent | random throwaway password + Odoo invitation token | end-to-end: "no password left on the control-plane record", "link is dead after first sign-in" |

End-to-end proof: `scripts/tenant_journey_ci.sh` (also a step in the
"Platform Odoo Install" workflow). It builds a throwaway control database,
runs the journey with provisioning disabled (no database may appear), runs it
again enabled (a real `stg_…` database), reads isolation from PostgreSQL,
starts an Odoo HTTP server on the tenant database and signs in through the
link. Result on the rig: see `MUMTAZ_PROGRESS_AND_HANDOFF.md`.

## 4. Design choices in slice 1, and why

| Choice | Reason | Alternative rejected |
| --- | --- | --- |
| The organization is a `res.partner` in the control database | Standard Odoo record; CRM, invoicing and contacts already work on it. Three organization-like models already exist; a fourth would repeat the mistake | Reusing `mumtaz.org` — it means "a company inside a shared database", the opposite of ADR-002, and drags website and CFO modules into the control database |
| Registration creates a request, not a tenant | A public form must not be able to create a database. A person approves | Provision on signup — abuse and cost risk; no email verification exists yet |
| Entitlement = a trial subscription resolved by the existing service | Reuses the control plane's own resolver; nothing parallel | A boolean on the request |
| First access by Odoo's invitation link | Signed by the tenant database's own secret, expires, void after first sign-in; no shared secret between tenants | `mumtaz_sso` — one secret for all tenants (ODOO-01) |
| The ERP profile carries no `mumtaz_core`, `mumtaz_branding`, `mumtaz_theme`, `mumtaz_sso` | `mumtaz_core` is an AI-settings module with a daily credential pull from a service that is not in the repository; the theme is the superseded gold palette; SSO is unsafe | Copying the `starter` bundle |
| Provisioning calls Odoo's internal create and initialise functions | The public wrapper refuses when the database manager is hidden, which is how a multi-tenant server must run | Requiring `list_db = True` in production |
| Staging databases are named `stg_…` | Backups, monitoring and clean-up can tell them apart by name alone | A flag only on the control-plane record |
| Product status is a field with a required explanation | The directive: do not mark a product operational because a screen looks right | Free-text status in a document |

## 5. What is not built (do not assume it works)

| Gap | Effect today | Next step |
| --- | --- | --- |
| The set-password link is stored on the tenant record, visible to platform administrators; it is not emailed | An operator must pass it to the customer | Email + resend from the control plane (needs a working outgoing mail server — UNKNOWN) |
| No captcha, no email verification on the public form | The route stays closed (`mumtaz_control_plane.public_signup` unset) | P-08 |
| No trial expiry handling for staging tenants | A trial subscription expires in the control plane; the database stays | P-07; lifecycle with no automatic deletion |
| Entitlements are not pushed into the tenant database | The tenant cannot gate features on its plan; `mumtaz.erp.module.access` exists but runs where it is installed | Tenant-side agent module (also the prerequisite for Jawhar and ZAKI) |
| Billing is not connected | Trial only; price is 0 | P-09, then Stripe tests |
| One PostgreSQL role for every database (REPORTED) | Isolation is by database, not by credential | P-17 |
| No localisation in the profile | A new tenant has no chart of accounts or VAT set-up | P-06, ERP backlog item 5 |
| Old bundles still pull the tenant registry into customer databases and name an Enterprise-only module | Anyone provisioning with `starter`, `growth`, `finance`, `ai_cfo` or `enterprise_partner` gets that result | Data fix + registry check (§7) |
| The company-per-org path (`mumtaz_org_config`) still has its own public signup | Two front doors with different tenancy | P-01 |
| "Mark Active" on the tenant form sets the state without any check | An operator can still declare a tenant active by hand | Decide whether manual activation is needed for databases created outside the control plane (UNKNOWN whether any exist) |
| Long provisioning runs in the wizard | A general ERP install takes about two minutes on the rig; an HTTP worker may be killed first | Use "Queue Provisioning"; the scheduled worker's time limit must allow several minutes (`limit_time_real_cron`) |
| Entitlement resolver answers "allowed" for a feature code it does not know | An unseeded feature (for example an AI quota) is unmetered | Fail closed for paid features, after an inventory of callers |

## 6. Before this is enabled on any server

Nothing below has been done, and none of it is to be done without the
owner's approval (directive §13).

1. Decide which Odoo instance and database is the control plane (P-02). It
   should hold only the control-plane modules, not a customer's ERP.
2. Verified backups exist for every production database (audit F-02, batch
   2B). Provisioning adds databases to the same PostgreSQL server.
3. Run `scripts/tenant_journey_ci.sh` against a staging instance on the
   target host. It only ever touches databases it creates.
4. Set `MUMTAZ_REAL_PROVISIONING=1` in that staging service's environment
   only. Without it, every run is a dry run and creates nothing.
5. Set the base domain (`mumtaz.erp_base_domain`), a wildcard DNS record and
   certificate for it, and the routing rule for `stg_…` databases
   (`mumtaz_subdomain_routing` or nginx). UNKNOWN today.
6. Upgrade path: `-u mumtaz_tenant_manager,mumtaz_control_plane` on the
   control database. Tested from `main` to this branch on the rig; existing
   tenant rows keep their state and get an empty `environment`.

## 7. Known defects left in place on purpose

The five older bundles are `noupdate` data and may be in use on a server
nobody here could inspect. They are documented, not edited:
`account_accountant` (Enterprise-only) in three of them;
`mumtaz_sme_profile`, `mumtaz_onboarding` or `mumtaz_voice` pulling the
tenant registry (and for `mumtaz_voice` the whole control plane) into the
customer database. Details and the proposed registry check that would catch
both: `MUMTAZ_MODULE_REGISTRY_REVIEW.md`.

## 8. Decisions needed

P-01 tenancy model · P-02 control-plane instance · P-03 where provisioning is
first enabled · P-04 organization of record · P-05 single sign-on · P-06
profile content and localisation · P-07 trial and staging lifecycle · P-08
opening public registration · P-09 price list · P-17 database roles and
backups. All in `docs/erp/project/DECISION_REGISTER.md`.

## 9. Files

| Area | Files |
| --- | --- |
| Provisioning | `addons/mumtaz_tenant_manager/services/provisioning.py`, `models/tenant_provisioning.py`, `wizards/provision_wizard.py`, `data/mumtaz_bundle_data.xml`, `tests/test_provisioning.py` |
| Catalogue, registration, entitlement gate | `addons/mumtaz_control_plane/models/product.py`, `models/signup_request.py`, `models/tenant_commercial.py`, `controllers/signup.py`, `data/product_catalogue.xml`, `views/product_views.xml`, `views/signup_request_views.xml`, `tests/test_signup_journey.py` |
| End-to-end check | `scripts/tenant_journey_ci.sh`, `scripts/tenant_journey/journey.py`, `scripts/tenant_journey/open_workspace.py`, `.github/workflows/platform-odoo-install.yml` |
