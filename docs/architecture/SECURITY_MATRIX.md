# Deliverable 8 — Security, approval and audit framework

Baselines: blueprint §10 (OWASP ASVS 5.0.0 application controls, NIST SP 800-218
SSDF). These are baselines, not certification.

---

## 1. AS-IS: what exists

**[FACT]** Measured at commit `1ea980a`:

| Control | State |
|---|---|
| `res.groups` defined | **30 distinct** (31 definitions — one duplicate, see §2) |
| `ir.model.access` rows | 222, covering **62 of 62** concrete models |
| `ir.rule` records | 35, covering **22 of 62** concrete models |
| Fields with `groups=` | 23 (11 credentials, 12 commercial in one module) |
| `company_dependent` fields | 0 |
| Fields with `tracking=True` | 139 |
| Role hierarchy via `implied_ids` | present in 10 modules |
| `.sudo()` call sites | 196 |
| Approval model / workflow | **none** |
| Delegation with start/end/reason | **none** |
| Audit-event model (§7.2) | **none** — chatter only |
| MFA for privileged operations | **not configured in code** |
| Rate limiting | `mumtaz_api_gateway` usage log only; no limiter |

## 2. Defect: two groups named "Super Admin"

**[FACT]**

```
addons/mumtaz_core/security/mumtaz_core_security.xml:44
    <record id="group_mumtaz_super_admin"> → name "Mumtaz / Super Admin"
addons/mumtaz_control_plane/security/security.xml:4
    <record id="group_mumtaz_super_admin"> → name "Mumtaz Super Admin"
```

These are **two different groups** — `mumtaz_core.group_mumtaz_super_admin` and
`mumtaz_control_plane.group_mumtaz_super_admin` — with names differing only by a
slash. In the Settings UI an administrator sees two nearly identical entries and
has no way to tell which grants what.

It is already load-bearing: the Stripe credential fields restrict to
`mumtaz_control_plane.group_mumtaz_super_admin` specifically. Granting the
`mumtaz_core` one instead silently fails to give access; granting both silently
gives more than intended.

**Fix:** rename one. `SEC-001` in the backlog. Trivial change, real risk.

## 3. The role model

**[FACT]** 30 groups across six families:

| Family | Groups |
|---|---|
| Platform | `mumtaz_super_admin` (×2), `mumtaz_platform_admin`, `mumtaz_platform_manager`, `mumtaz_support_admin`, `mumtaz_ops_readonly`, `mumtaz_manager`, `mumtaz_analyst` |
| Tenant / SaaS | `mumtaz_tenant_admin`, `mumtaz_billing_admin`, `mumtaz_sme_admin`, `mumtaz_partner_manager` |
| Finance | `mumtaz_finance_user`, `mumtaz_cfo_user`, `mumtaz_cfo_manager` |
| Delivery | `c2p_delivery_member`, `c2p_delivery_lead`, `c2p_portfolio_manager` |
| Growth | `lead_scraper_viewer/user/admin`, `lead_nurture_user/manager`, `media_user`, `media_manager` |
| Portal gateway | `portal_gateway_admin/erp/zaki/marketplace` |
| Marketplace | `marketplace_user`, `marketplace_manager` |

**[DESIGN] The structure is reasonable; the gap is segregation of duties.**
Blueprint §10.1 requires requester, approver, payer, invoice-poster and
inventory-adjuster to be separable, with no silent self-approval. Nothing in the
30 groups expresses an *approver* role, and with no approval record there is
nothing to segregate. The ERP-facing side will inherit `account`'s own groups
(`account.group_account_invoice`, `_manager`, `_user`) — which is correct and
should be relied on rather than duplicated.

## 4. TO-BE access matrix

**[DESIGN]** Proposed, not approved. Adapt to the signed authorisation matrix
(DEC-006). Standard Odoo groups are used wherever they exist, per blueprint §17.

| Action | Delivery Member | Delivery Lead | Portfolio Mgr | Finance User | CFO Mgr | Platform Admin | Ops Readonly |
|---|---|---|---|---|---|---|---|
| Read own project / tasks | Own | Team | All | — | All | All | Read |
| Edit task, set milestone | Own | Team | All | — | — | — | — |
| Read project commercials (`groups=COMMERCIAL`) | **No** | **No** | Yes | Yes | Yes | Yes | **No** |
| Edit contract value | No | No | Yes | No | Yes | No | No |
| Reset milestone baseline | No | No | Yes | No | No | No | No |
| Create quotation | — | — | — | `sale` std | — | — | Read |
| Approve discount above threshold | No | No | Threshold | No | Higher | No | Read |
| Post customer invoice | No | No | No | `account.group_account_invoice` | Yes | No | Read |
| Approve write-off | No | No | No | Within policy | Higher | No | Read |
| Change fiscal lock date | No | No | No | No | Yes + logged | No | Read |
| Read tenant subscription / billing | No | No | No | No | No | Yes | Read |
| Read a credential field | No | No | No | No | No | **No** | **No** |
| Manage role grants | No | No | No | No | No | **Separate security admin** | Review |
| Cross-company aggregate (totals only) | No | No | Yes | Yes | Yes | Yes | No |
| Cross-company record detail | No | No | **No** | No | No | No | No |

Two rows carry the design's whole intent:

- **"Read a credential field" is No for every role including Platform Admin.**
  Credentials should be write-only from the UI: settable, never readable back.
  Today they are `groups=`-restricted but readable by the holder of that group.
- **"Cross-company record detail" is No for everyone.** `c2p_project_tracker`
  already enforces this — aggregates cross the boundary, records never do, and
  restricted money keys are *omitted* from the payload rather than zeroed. Keep
  that as the platform-wide rule.

## 5. Approval framework

**[DESIGN]** Blueprint §8 item 3 and §10.1. Build on the standard ladder, not a
new model first (`FIT_GAP_REGISTER.md` §6):

1. **Rung 1 — configuration.** Odoo Automation Rules + `mail.activity` for
   approval requests. Covers discount thresholds, change requests, baseline
   resets. **No code.**
2. **Rung 2 — standard.** `account`'s own controls for invoice posting and lock
   dates; `purchase`'s bill-control policy for 3-way match.
3. **Rung 3 — small add-on.** Only if 1 and 2 fail: the `approval_state` /
   `approved_by` / `approved_at` triple on the §7.1 mixin (`ARCH-001`), with a
   constraint that `approved_by != create_uid` to make self-approval impossible
   rather than merely discouraged.

Every approval records actor, timestamp, reason and before/after state.

## 6. Audit framework

**[FACT]** 139 fields carry `tracking=True`, so Odoo's chatter records changes to
them. That is a real audit trail and it is more than most projects have.

**[DESIGN] What is missing** (blueprint §7.2's audit-event contract): no
`correlation_id`, no retention or immutability policy, no redaction policy for
sensitive values, no record of *reads* (so a mass export leaves no trace), and no
audit on the 839 untracked fields.

Minimum additions:

| Need | Approach |
|---|---|
| Correlation across a request | `correlation_id` on the §7.1 mixin, set from the HTTP request |
| Export / mass-read trail | Log `ir.exports` and `read_group` on restricted models |
| Retention + immutability | Policy document + an archive job; never delete fiscal evidence |
| Redaction | Credential fields excluded from tracking by construction |
| AI action provenance | See §7 |

## 7. AI governance — the largest unmitigated risk

**[FACT]** `mumtaz_ai` (7 models), `mumtaz_voice` (5 models), `mumtaz_zaki`
(5 models) are live AI surfaces. `mumtaz_ai` carries **2 references to `account`**.
`c2p-delivery-system` is a full LLM pipeline that reaches Odoo over XML-RPC and
pushes code to GitHub.

**[FACT]** Blueprint §12 requires, per agent: permitted tools and data, named
service identity, user delegation, prompt-injection controls, grounding,
confidence, sources, company boundary, approval workflow, dry-run, audit logging,
rate and spend limits, retries, evaluation corpus, failure mode, rollback and kill
switch.

**Present:** approval gates in `delivery_api/policy.py` (`config_apply`,
`code_deploy`, `proposal_send`), deterministic local fallbacks at every stage, run
logging in `llm.py`.

**Absent:** action classification, named service identity per agent (agents act as
a human's session or as admin), dry-run, spend limit, kill switch, evaluation
corpus, prompt-injection controls, and any audit record on the Odoo side
distinguishing an AI-originated change from a human one.

**[DESIGN] Three controls, in order:**

1. **Classify every agent action** as read-only / recommend / draft /
   act-with-approval, in code, as an enum on the agent model. Anything touching
   `account` is act-with-approval or it does not ship.
2. **A named service user per agent**, with its own group granting the minimum
   models — never `base.group_system`, never a human's session. This also makes
   the audit trail work for free: the actor on the record *is* the agent.
3. **A kill switch** — one boolean on `mumtaz.core.settings`, checked before every
   outbound call, `base.group_system`-restricted.

`SEC-002`, `SEC-003`, `SEC-004`.

## 8. Operational security

**[FACT, prior session]** Outstanding and unremediated: direct inbound access to
Odoo application ports from any address, and an internet-reachable instance able
to select a live business database protected by a default-strength administrator
credential. Details are in the session history, deliberately not in this
repository.

**This is `SEC-000` — the first item in the backlog, ahead of all development.**
It needs no decision, no design and no code; it needs a firewall rule and a
password change. Every control described above is theatre until it is done.

## 9. Testing security

Blueprint §15.1 role/security layer. **Zero security tests exist outside
`c2p_project_tracker/tests/test_security.py`, and that file has not been run.**

Required per slice:
- one positive test per role,
- one **negative** test proving the wrong role is refused by the *server*,
- one cross-company test (two users, two companies, same record id),
- one privilege-escalation attempt (horizontal and vertical).

A security control with no negative test is an assumption.
