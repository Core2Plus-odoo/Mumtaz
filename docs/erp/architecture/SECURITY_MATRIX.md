# 8a. Security, approval and audit framework

Baseline: OWASP ASVS 5.0 controls where they apply to an Odoo deployment;
NIST SSDF practices in the delivery process (`DEVELOPMENT_STANDARDS.md`).
This is a design and a current-state record, not a certification.

## 8a.1 Identity and tenancy [VERIFIED / PROPOSED]

| Control | Today | Target |
| --- | --- | --- |
| Identity authority | Odoo users per tenant database; zaki-server caches users in SQLite and issues JWTs; HMAC SSO from the control panel | Odoo remains the authority; JWT only as a session carrier; retire the SQLite cache (D-05) |
| Tenant isolation | one database per tenant; `mumtaz_subdomain_routing` picks the database by host | keep; add a test that a host cannot reach another database |
| Company isolation inside a tenant | record rules on Jawhar models (tested); `company_ids` rules on standard models; platform models partly unscoped | `company_id` + rule on every custom transactional model; one negative test per module (two users, two companies, same record id → 404) |
| MFA | not enforced | `auth_totp` mandatory for manager, finance and admin groups [DECISION ADR-009] |
| Service identities | zaki-server uses the admin uid over XML-RPC; C2P delivery uses an encrypted connection record | a named service user per integration with the minimum groups; never `admin` |
| `sudo()` | 56 uses in platform modules; Jawhar uses it for public doors with narrow reads | every use carries a comment `# sudo: <reason>`; the list below is kept current; CI greps for undocumented uses |

## 8a.2 Role model (target) [PROPOSED]

| Object / operation | Staff | Dept manager | Warehouse | Accountant | Controller | Admin | Auditor | Company filter | VIP manager (Jawhar) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Customer master read/write | own/team | yes | read | read | read | yes | read | yes | restricted tiers only |
| Discount above threshold | no | threshold | no | no | higher threshold | no | read | yes | n/a (making only) |
| Sales order confirmation | yes | yes | no | no | no | yes | read | yes | |
| Goods issue / stock adjustment | request | no | authorised | no | approve adjustments | yes | read | yes | |
| Invoice posting / reversal | no | no | no | authorised | authorised | yes | read | yes | |
| Bank payment creation / release | no | no | no | create | release | yes | read | yes | |
| Period lock change | no | no | no | no | authorised + logged | no | read | yes | |
| Gold rate approve (Jawhar) | no | maker or checker, never both | no | no | no | no | read | yes | no (tested) |
| AI draft approve | no | yes, not own | no | no | yes | no | read | yes | restricted clients |
| Export of partner lists | no | logged | no | logged | logged | logged | logged | yes | logged (tested) |
| Role and company grants | no | no | no | no | no | security admin | review | | |
| Tenant feature toggles / billing | no | no | no | no | no | platform admin only | | n/a | |

Segregation of duties enforced in code today [VERIFIED]: rate maker ≠ checker;
exchange above threshold needs a manager who is not the creator; AI draft
author ≠ approver; VIP manager does not imply jewellery manager (test).

## 8a.3 Audit trail

| Event | Store | Status |
| --- | --- | --- |
| Every Jawhar API call incl. failed sign-ins | `jewellery.api.audit` | proven |
| Read of a restricted client (form, list, export) | `jewellery.vip.access.log` | proven (widened 20 Nov) |
| Agent runs, refusals, drafts | `jewellery.ai.run`, `.draft` | proven |
| AML events | `jewellery.aml.event` | proven |
| Field changes on transactional models | `mail.thread` tracking | partial (19 tracked fields in platform modules); target: state and money fields everywhere |
| Control-plane commercial events | `mumtaz.commercial.event.log`, subscription lifecycle logs | exists, untested |
| Server-side ledger changes | Odoo `account.move` chatter; no deletion of posted moves | standard |

Retention: audit rows are never deleted by code; retention periods are a
finance/legal decision (CLAUDE.md jewel rule: compliance values are
configuration).

## 8a.4 Mandatory negative tests (per module, before "done")

1. Cross-company read, write, export and report by a user of another company.
2. Horizontal enumeration of record ids through the API (404 not 403: Jawhar pattern).
3. Hidden action executed directly through RPC.
4. Self-approval on every approval path.
5. Integration key reuse / replayed webhook.
6. Agent service account attempting a prohibited write.

## 8a.5 `sudo()` inventory (completed 21 Nov 2026, backlog item 3)

The audit's first count (56) covered five modules. The full count is **298
call sites in 34 modules** (tests excluded). Every one now carries a
`# sudo: <reason>` label on the line above it, and `scripts/check_sudo.py`
fails the lint job on any unlabelled call. Reasons fall into these classes:

| Class | Typical reason | Verdict |
| --- | --- | --- |
| System parameters | `ir.config_parameter` reads that only administrators may do | Justified |
| Append-only logs | audit, AML, access, run, billing and usage rows the acting user may not create | Justified |
| Public doors | kiosk, client app, tray link, website forms, organisation pages: narrow reads keyed by serial, token, phone or slug; requests created after validation and caps | Justified; tested for the Jawhar doors |
| Business actions on stock | memos, transfers, imports, counter: stock moves written by the action for staff without stock rights; locations fixed by the action | Justified |
| Cross-company and aggregate reads | owner cards, store summaries, C2P tracker reading the delivery company; figures, counts and names only | Justified |
| Entitlements and group membership | feature-access resolution and group writes done by the control plane | Justified |
| Payment and tenant state | Stripe webhook (signature-verified), card page (gated), provisioning | Justified |
| **REVIEW-01** | `mumtaz_app_portal` and `mumtaz_portal_routing` dashboards read business data with `sudo()` on routes open to any `auth='user'` session, portal users included | **Closed 21 Nov 2026**: portal users redirected to `/my`; 34 `sudo()` calls dropped so business data is read as the user; control-plane rows keep `sudo()`; 5 tests |
| **REVIEW-03** | `mumtaz_zaki` `/zaki/api/snapshot` returned a finance snapshot to any `auth='user'` session | **Closed 21 Nov 2026**: portal users and users without an accounting group are refused before any query; 2 tests |
| **REVIEW-04** | `c2p_command_center` aggregates across companies with `sudo()` | **Closed by evidence 21 Nov 2026**: `get_data()` checks the command-centre group on every call, the menu is restricted to it; 2 tests |
| **REVIEW-05** | Modules brought from the production server on 21 Nov 2026 (`c2p_appointment`, `c2p_master_agent`) carry 20 `sudo()` calls with no recorded reason; `c2p_appointment` creates leads and calendar events from a public website route; `c2p_master_agent` calls `urlopen` on a URL read from a system parameter without checking its scheme | **Open.** Each call needs a reason or removal; the public booking route needs a cross-company and rate-limit review; validate the Ollama URL scheme |

Sites per module:

| Module | `sudo()` sites |
| --- | --- |
| `mumtaz_app_portal` | 23 |
| `mumtaz_portal_routing` | 23 |
| `mumtaz_control_plane` | 21 |
| `mumtaz_jewellery_client` | 17 |
| `c2p_command_center` | 16 |
| `mumtaz_billing_stripe` | 16 |
| `c2p_project_tracker` | 12 |
| `mumtaz_jewellery_vip` | 12 |
| `mumtaz_marketplace` | 12 |
| `mumtaz_jewellery_aml` | 11 |
| `mumtaz_jewellery_crm` | 11 |
| `mumtaz_jewellery_stores` | 10 |
| `mumtaz_api` | 9 |
| `mumtaz_core` | 9 |
| `mumtaz_vendor_portal` | 9 |
| `mumtaz_jewellery` | 8 |
| `mumtaz_jewellery_owner` | 8 |
| `mumtaz_org_config` | 8 |
| `mumtaz_organization` | 8 |
| `mumtaz_jewellery_channels` | 6 |
| `mumtaz_jewellery_demo` | 6 |
| `mumtaz_jewellery_kiosk` | 6 |
| `mumtaz_api_gateway` | 5 |
| `mumtaz_jewellery_ai` | 5 |
| `mumtaz_jewellery_outreach` | 5 |
| `mumtaz_cfo_base` | 4 |
| `mumtaz_subdomain_routing` | 4 |
| `mumtaz_zaki` | 4 |
| `mumtaz_voice` | 3 |
| `mumtaz_jewellery_api` | 2 |
| `mumtaz_jewellery_sale` | 2 |
| `mumtaz_sso` | 1 |
| `mumtaz_tenant_manager` | 1 |
| `mumtaz_website` | 1 |

The three REVIEW items are closed (backlog item 2, first part); 264 labelled
calls remain. A label is not a licence: a reviewed call may still be removed
when the user's own rights are enough, as 34 of them were.
