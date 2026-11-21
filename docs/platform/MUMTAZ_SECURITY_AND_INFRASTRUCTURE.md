# Mumtaz security and infrastructure — reconciliation

Written 21 Nov 2026. This is a pointer and a delta, not a second security audit.

## Conclusion

1. The two most serious risks are on the server and are **still open**: application ports and a client ledger reported reachable from the internet over plain HTTP with a weak administrator credential, and no verified backup of any production data. Neither can be fixed from the repository.
2. Code-level risks are being closed one pull request at a time. Three are closed on `main`, one is closed in code but not confirmed deployed, three remain open.
3. Slice 1 on this branch adds a provisioning path that was built to be safe by default: closed until switched on, a person approves before anything is created, no password is stored or sent, and nothing is deleted automatically. It does not solve shared database credentials, backups or single sign-on.

## Status legend

| Tag | Meaning |
|---|---|
| **VERIFIED** | Read in code at the cited path, or run on the local Odoo 19 rig on 21 Nov 2026 |
| **REPORTED** | From a repository document or an earlier session note. Includes everything about the live server |
| **PROPOSED** | Recommended, not built or not decided |
| **UNKNOWN** | Needs server evidence or an owner decision |

## 1. Authoritative documents

| Subject | Document |
|---|---|
| Security findings, all severities, with evidence | [`docs/infrastructure-audit/04_SECURITY_AUDIT.md`](../infrastructure-audit/04_SECURITY_AUDIT.md) |
| Databases, roles, stray copies | [`05_DATABASE_AUDIT.md`](../infrastructure-audit/05_DATABASE_AUDIT.md) |
| Backup and recovery | [`09_BACKUP_AND_RECOVERY_AUDIT.md`](../infrastructure-audit/09_BACKUP_AND_RECOVERY_AUDIT.md) |
| Remediation backlog and the read-only server check | [`13_REMEDIATION_BACKLOG.md`](../infrastructure-audit/13_REMEDIATION_BACKLOG.md) |
| Decisions, approvals, and what changed on `main` after the audit | [`15_DECISIONS_AND_APPROVALS.md`](../infrastructure-audit/15_DECISIONS_AND_APPROVALS.md) |
| Identity, roles, audit trail, `sudo()` inventory, review items | [`docs/erp/architecture/SECURITY_MATRIX.md`](../erp/architecture/SECURITY_MATRIX.md) |
| Target infrastructure | [`11_TARGET_ARCHITECTURE.md`](../infrastructure-audit/11_TARGET_ARCHITECTURE.md) |

## 2. Top risks, in priority order

| # | Risk | Finding | Status on 21 Nov 2026 | Tag |
|---|---|---|---|---|
| 1 | Odoo application ports reachable from the internet; the external client's accounting used over plain HTTP on a raw port; one reachable instance with a default-strength administrator credential | F-01 | **Open.** Server-side; backlog S-02 to S-05. The credential change needs no restart and is the owner's first action | REPORTED |
| 2 | No verified, restorable, off-site backup of any production database, filestore or application store. The scheduled backup workflow has never run | F-02 | **Open.** Backlog B-01 to B-07. Nothing on the server should be changed before a restore-tested backup exists | REPORTED (server) / VERIFIED (workflow cannot parse) |
| 3 | One shared sign-on secret is copied into every provisioned tenant database; a token naming any database and any login is accepted | F-23, ODOO-01 | **Open.** `mumtaz_sso` unchanged. Slice 1 does not use it and does not install it in the new ERP profile. Redesign is decision P-05. Whether it is installed anywhere is UNKNOWN | VERIFIED in code |
| 4 | The ZAKI FastAPI back end has no authentication and uses one administrator account for every tenant | F-24, APP-01, APP-02 | **Open in code.** Verdict: retire, do not deploy ([`MUMTAZ_AI_ARCHITECTURE.md`](MUMTAZ_AI_ARCHITECTURE.md)). Whether it runs is UNKNOWN | VERIFIED in code |
| 5 | Any signed-in user, portal included, can rewrite group membership or drive the payment-provider key over RPC | F-27, ODOO-02, ODOO-03 | **Open.** The methods are still public | VERIFIED in code |
| 6 | The repository is public and describes the server layout, database names and client details | F-03 | **Accepted by the owner** on 21 Nov 2026 (audit D-01: keep public, because the working method requires it). This raises the urgency of rows 1 and 2; it does not close them | VERIFIED |
| 7 | Delivery console: authentication is opt-in and fails open; stored credentials can be redirected | F-28, C2P-01 to C2P-05 | **Open.** Which mode production runs in is UNKNOWN (V-12) | VERIFIED in code |
| 8 | All native Odoo instances except Faizy share one PostgreSQL role, one OS user and one data directory | F-06 | **Open.** Backlog R-13; decision P-17 before a paying tenant | REPORTED |

Closed or addressed since the audit:

| Finding | Status | By | Tag |
|---|---|---|---|
| ODOO-04 — finance snapshot open to any signed-in user | Addressed: portal users and non-accounting users refused; tests added. The route still reads under `sudo()` with no company filter | PR #175 | VERIFIED |
| ODOO-05 — portal dashboards read under `sudo()` | Addressed: read as the signed-in user; tests added | PR #175 | VERIFIED |
| `sudo()` overuse | Every call carries a reason; enforced in CI by `scripts/check_sudo.py` (296 calls on this branch, all labelled) | PR #174 | VERIFIED |
| F-09 — default branch red, no install test for platform modules | Fixed | PR #170, #172 | VERIFIED |
| F-05 — production modules that existed only on the server | Largely addressed; review item REVIEW-05 open; 25 database-stored CRM rules still outside git | PR #180 | VERIFIED / REPORTED |
| ODOO-06 — Faizy identity documents readable by every customer | Fixed in code with tests, on `main` and on the Faizy production branch. Deployment to the server is UNKNOWN | PR #182, #184 | VERIFIED code |

## 3. Security properties of slice 1

All VERIFIED by automated tests on this branch (`addons/mumtaz_tenant_manager/tests/`, `addons/mumtaz_control_plane/tests/`, `scripts/tenant_journey_ci.sh`).

| Property | How it is enforced |
|---|---|
| Only platform administrators can create a tenant database | Queueing and the provision wizard check for the Platform Administrator or system administrator group. A Platform Manager, who may edit tenant records, is refused even over RPC |
| Only a Mumtaz Super Admin can approve a registration or start its provisioning | Checked in the request's own methods, not only by hiding buttons |
| A server creates databases only when explicitly allowed | Environment switch `MUMTAZ_REAL_PROVISIONING=1`. Without it, a real run is refused and the queue only simulates |
| A simulation can never look like a live tenant | A dry run leaves the tenant in draft and the request in "approved". Only a real run that passed verification sets "active" |
| The public registration route is closed by default | It answers only when a system parameter is set. Tested closed and open |
| The public route cannot create anything but a pending request | No tenant, subscription or database until a person approves |
| Abuse limits on the public route | Hourly cap on public requests; a hidden field that only automated senders fill; a repeat from the same email gets the same answer as a new request, so the form does not reveal who has registered |
| No password is stored or transmitted by the registration journey | The administrator account gets a random password that nobody sees. Access is through Odoo's own one-time invitation link, signed by the tenant database, time-limited, and void after the first sign-in (replay tested over HTTP) |
| The invitation link is treated as a credential | Stored in a field readable by platform administrators only; never written to the provisioning log |
| Provisioning does not need the database manager exposed | The end-to-end check runs with the database list hidden |
| Nothing is deleted automatically | A failed run that created a database flags it for a person; a retry is blocked until someone has dealt with it |
| Staging data is identifiable by name | Staging tenant databases must start with `stg_`; production ones must not |
| Customer databases hold no control-plane data | The ERP profile's dependency closure is tested; the end-to-end check confirms no tenant-registry, plan or subscription tables in the tenant database |
| Provisioning requires an entitlement | Refused unless the shared entitlement resolver grants the product's access feature; a suspended subscription blocks it |

## 4. What slice 1 does not solve

| Gap | Why it matters | Next step | Tag |
|---|---|---|---|
| One PostgreSQL role for all databases on the server | "Isolated database" is separation by database, not by credential. A fault in one Odoo process can reach every database that role owns | Per-tenant or per-instance role before any paying tenant (P-17, backlog R-13) | REPORTED |
| No backups | A provisioned tenant has no restore point | Backlog B-01 to B-07 first (P-17) | REPORTED |
| The invitation link is not emailed | An operator must copy it from the tenant record to the customer | Send it from the control plane once outbound mail is confirmed | VERIFIED |
| No captcha or email verification on the public form | The hourly cap limits volume; it does not prove a person or an address | Add both before the form is switched on in production | VERIFIED |
| Long provisioning runs and worker time limits | A general ERP database takes about two minutes locally. Run inline in the wizard it can exceed an HTTP worker's time limit and leave a half-built database | Use the queue; set the scheduled-job time limit on the control-plane instance to several minutes | VERIFIED locally / UNKNOWN on the server |
| Single sign-on | The shared-secret bridge is unsafe (row 3). Today the customer signs in to their workspace directly | Redesign (P-05): per-tenant keys or a standard protocol | PROPOSED |
| The entitlement resolver answers "allowed" for an unregistered feature code | A typo in a feature code grants access | Fail closed for paid features, after the four calling modules are checked | VERIFIED |
| "Mark Active" by hand | An operator can still mark a tenant active without a database | Decide once the server shows whether manually built tenants exist | VERIFIED |
| The older bundles | Four of five install control-plane modules into the customer database | Correct them after the server inventory ([`MUMTAZ_MODULE_REGISTRY_REVIEW.md`](MUMTAZ_MODULE_REGISTRY_REVIEW.md)) | VERIFIED |

## 5. Standing rules

From the consolidation directive, section 13, unchanged:

> **MANDATORY PRODUCTION SAFETY — This rule overrides development speed.** Do not: Delete databases. Rename installed modules directly. Change production configurations during discovery. Modify customer business data. Overwrite existing websites. Merge C2P and IG2 databases. Replace working applications without regression testing. Deploy untested code. Perform destructive migrations without explicit authorization. Disrupt current customer operations. Use feature branches, isolated staging environments, verified backups and documented rollback procedures. Do not make production changes without explicit approval.

Also in force: the twenty operating rules of the infrastructure audit (audit first; never restart, migrate, deploy or change routing without approval; never claim a backup is recoverable or a vulnerability confirmed without evidence). For AI: no unrestricted SQL and no administrative Odoo access for agents; banking pilots read-only. For the external client's system: no automatic change without a compatibility test and approval. No claim of certification or compliance without evidence.

Nothing in this session changed any server, database, DNS record, credential or running service.

## 6. Owner actions still open

| Action | Why it is the owner's | Reference |
|---|---|---|
| Change the default-strength Odoo administrator password on every instance | A credential change inside Odoo; needs no restart | S-02 |
| Delete two stale branches: `claude/html-creation-7knykl` and the merged `claude/faizy-document-access` | The session's credentials may push only to its own branch | audit D-10 |
| Run the read-only verification pack on the VPS and return the output privately | Nobody else has server access | V-01 to V-12 |
| Name a business owner and a technical owner per system | Every approval needs a name | audit D-02 |
| Take and restore-test one backup of each production database before any server change | Precondition for every remediation batch | B-02, B-03 |
| Back up `faizy_prod`, then upgrade `faizy_core` so the document rule takes effect | The fix is merged but not confirmed deployed | PR #184 |
| Decide P-02 (which instance is the control plane), P-03 (where real provisioning is enabled first), P-05 (sign-on), P-17 (database roles and backups before a paying tenant) | Architecture and risk decisions | `docs/erp/project/DECISION_REGISTER.md` |
