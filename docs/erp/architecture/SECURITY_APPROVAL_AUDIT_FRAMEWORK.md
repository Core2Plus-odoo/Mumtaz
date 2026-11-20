# 08. Security, approval and audit framework

Baselines (blueprint §10): OWASP ASVS and NIST SSDF as design baselines, **not certifications**. Facts are `[V]` from `ir.model.access.csv`, group XML and method code; proposals are `[P]`; policy numbers that only the business can set are `[D]`.

## 1. Role model

| Role | Implemented as `[V]` | Implies | Purpose |
| --- | --- | --- | --- |
| Pharma Operations User | `pharma_core.group_pharma_user` | base | Read the pharma apps; take ownership of exceptions |
| Finance Controller | `group_pharma_finance` | Operations | Upload/build statements, post and reconcile remittances, create draft COD entries, propose closure of exceptions, edit the Commercial Model |
| Tax Approver | `group_pharma_tax_approver` | Operations | Approve tax rules and SKU classifications (never their own) |
| Pharma Administrator | `group_pharma_admin` | Operations | Draft tax rules (maker), manage couriers and their accounts, Source Events |
| **Accountant** | Odoo `account.group_account_invoice` (not a pharma group) | n/a | **Posts** every COD entry; needs the Pharma user role to see the app |
| **Auditor** | **does not exist** `[P]` | read-only across apps and entries | Required by the blueprint matrix (gap G-6) |
| Security administrator | Odoo settings admin | n/a | Role grants; should be separate from finance and admin `[P]` |

## 2. Access matrix as implemented (`[V]` from the ACL rows)

R = read, W = write, C = create, D = delete; "–" = none.

| Model | Operations | Finance | Tax Approver | Pharma Admin |
| --- | --- | --- | --- | --- |
| `pharma.raw.event` (immutable) | R | RWC | | |
| `pharma.tax.rule` | R | | RWC | RWC |
| `pharma.tax.event` | R | | | |
| `pharma.recon.run`, `.item` | R | RWC | | |
| `pharma.recon.exception` | **RWC** `[note 1]` | RWC | | |
| `pharma.partner.stock.line`, `.scenario` | R | RWC | | |
| `pharma.courier` | R | R | | RWCD |
| `pharma.courier.shipment` | R | RWC (no delete) | | |
| `pharma.courier.remittance`, `.line`, `.statement`, `.statement.line` | R | RWCD (drafts only, enforced in code) | | |
| `pharma.courier.entry.reverse` (wizard) | | RWCD | | |

`[note 1]` Operations can create and write exceptions. Plausibly intentional (take ownership, add notes) but the closure path is maker-checker in code; the exact write surface must be reviewed and either narrowed with field-level control or documented (backlog PHA-SEC-002).

## 3. Segregation of duties `[V]` unless marked

| Control | Enforcement | Negative test |
| --- | --- | --- |
| Tax rule: maker ≠ approver; evidence/legal refs required to approve | method checks in `pharma_pk_tax_core` | present (DEMO T2, T3, T6b) |
| Exception closure: proposer ≠ approver, second controller | `pharma_reconciliation_hub` methods | present |
| Statement build, remittance post/reconcile: Finance only | `has_group` inside each action | present |
| **Finance creates draft entries; only an accountant posts** | Finance has no Accounting group (asserted by test); entries created `draft` with elevated rights but the real user as creator | present |
| Strict order: slip settled only after every parcel has a posted collection entry; override needs a written, logged reason | `_check_flow_order` | written, NOT RUN |
| Withdrawing a posted entry: Finance requests with a reason; accountant posts the reversal; release only after the reversal posts | reversal mixin | written, NOT RUN |
| Self-approval of any kind outside the two maker-checker flows | **not covered** | gap |
| Change of the process mode (`pharma.cod_flow_mode`), courier accounts, authorized deductions | system parameter / courier form, **no dedicated audit trail** | gap `[P]` SEC-004: log changes, print the mode in `verify` |

## 4. Approval framework `[P]` (thresholds `[D]`)

A single generic approval mixin, replacing per-model code, with: required approver group, **threshold bands** (amount or risk), delegation with start/end/reason, an approval log, and a rule that requester ≠ approver ≠ poster. Bands are blank in this document on purpose: the business sets them (discount override, write-off, stock adjustment, period-lock change, deductions above the authorized amount, reversal of a posted entry). Odoo Community has no approvals app, so this is a justified custom gap (ADR-007).

## 5. Audit evidence

| Evidence | Where `[V]` | Gap |
| --- | --- | --- |
| Who changed key fields | `tracking=True` on parcels, remittances, statements, rules | Courier account configuration and process-mode parameter are not tracked |
| Immutable source data | `pharma.raw.event` (no edit, no delete; conflict state) | Retention and export policy undefined |
| Why an override/reversal | override reason and reversal reason logged on the record's chatter | NOT RUN |
| Who created an entry | `create_uid` is the Finance user although creation uses elevated rights | Needs an Entries-to-Post view that shows it (written) |
| Entry provenance | COD entries carry `pharma_cod_kind` and source links (written) | Audit-event view not built `[P]` |
| Access logs | Odoo/nginx logs on the VPS | No review procedure |

## 6. Mandatory negative tests (pack template) and status

| Test | Status |
| --- | --- |
| Unauthorized cross-company read/write/export/report | **Cannot be tested: no company scope exists** (G-1) |
| Horizontal record enumeration by ID | not tested |
| Hidden action executed by RPC (button hidden, method called) | covered per action by in-method group checks; no RPC-level suite |
| Self-approval | covered for the two maker-checker flows only |
| Delegation expiry | N/A (no delegation) |
| Compromised integration key | not tested (platform scope) |
| Agent service account attempting forbidden writes | not applicable until an agent exists |

## 7. Privacy, secrets and data classes `[P]`

Classes: public · internal · confidential (customer contact and address, COD amounts) · restricted (bank accounts, tax IDs, salaries). Secrets: environment files only, encrypted at rest where stored, never echoed or committed; the deployment procedure types credentials interactively on the host. Exports (the COD accounting kit's Excel route) are guarded by the hardening module. Demo data is fictional and flagged; `pharma.mode=production` refuses demo tax rules.

## 8. AI and automation controls `[P]` (blueprint §12)

| Class | Allowed examples here | Rule |
| --- | --- | --- |
| Read only | summarize a courier's overdue parcels | scoped service identity, no broader than the user |
| Recommend | flag courier shortfall trends, rank the work queue | cite the records; confidence stated |
| Draft | draft a chase message, draft a collection entry for Finance | stays a draft; deterministic validation before any save |
| Act with approval | create statement rows from a file | explicit role approval, dry-run, full provenance |
| **Prohibited** | post entries, approve tax rules, change roles, pay, delete, mass-export | enforced by *not granting* the rights, not by prompt wording |

Every agent needs: named scoped identity, tool allow-list, prompt-injection handling for uploaded files, rate/spend limit, evaluation set, audit log, kill switch. None exists yet; `mumtaz_ai` / `_voice` must be audited against this before extension (backlog AI-001).
