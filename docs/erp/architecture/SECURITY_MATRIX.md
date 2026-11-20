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

## 8a.5 `sudo()` inventory (to be completed in Wave 1)

| Module | Count | Justified in code | Action |
| --- | --- | --- | --- |
| `mumtaz_control_plane` | 21 | no | document or remove |
| `mumtaz_marketplace` | 12 | no | document or remove |
| `mumtaz_vendor_portal` | 9 | no | document or remove |
| `mumtaz_einvoicing` | 0 | no | document or remove |
| `mumtaz_api`, `mumtaz_api_gateway` | 9 + 5 | no | document or remove |
| Jawhar modules | public doors only | yes (narrow reads, serial-addressed) | keep |
