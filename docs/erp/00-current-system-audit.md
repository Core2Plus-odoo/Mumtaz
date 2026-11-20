# IG Square ERP — Current-System Audit (Gate G0)

**Target system:** `Mumtaz_IG2` (IG Square Pakistan) · Odoo 19 · VPS 187.77.128.199
**Standard applied:** ERP Master Blueprint v1.0 (`docs/ERP_MASTER_BLUEPRINT.md` in the pack)
**Prepared:** 2026-11-20 · **Status:** draft for sponsor review
**Legend:** ✅ VERIFIED (observed this engagement) · 🔎 TO-VERIFY (needs the discovery script in §6) · 💡 PROPOSED · ⚠️ DECISION NEEDED

> Per blueprint §2/§21, nothing below is coded. This is the current-state audit and the basis for the fit-gap and roadmap. "Unknown is not approved."

## 1. Business context (✅ from this engagement)
- **Entity:** IG Square Pakistan (Private) Limited — **media / advertising agency**, Karachi (SRB/Sindh sales tax; "Karachi Office" in narrations).
- **Group:** sister company **Mesh Media (Private) Limited** lives in the **same** `Mumtaz_IG2` database (multi-company).
- **Model:** media buying/placement + digital marketing; trade discounts and BD/rebate pass-backs to clients; content trading. Clients are major PK brands (Nishat, Haier, Hamdard, Orient, Stylo, Sana Safinaz, Treet, Packages, etc.) + Spotify MENA.
- **Finance:** Khurram Qabil (finance); vouchers prepared by Behroz Khan.

## 2. Platform & deployment (✅ unless marked)
- **ERP:** Odoo **19**, **Community** 🔎 (served from the Odoo nightly deb repo).
- **DB:** `Mumtaz_IG2`; served by systemd `odoo3` on `127.0.0.1→0.0.0.0:8071`, `dbfilter = ^Mumtaz_IG2$`, `proxy_mode = True`, `list_db = False`.
- **Other instances on the box (✅):** `odoo` (:8069), `odoo2` (Mumtaz_ERP :8070), `odoo4` (Mumtaz_C2P :8075). Shared Postgres. `odoo3` cron currently also polls other DBs incl. a dead `scratch_pre` (log noise — hygiene item).
- **Access:** direct IP:8071 over **plain HTTP** (no TLS); `mumtaz.digital` lapsed. ufw opens 8071 (was lost once in an update; re-added).
- **Code of record:** GitHub `core2plus-odoo/mumtaz`, branch `claude/resume-help-95ne9v`; deploy = `git pull` on the VPS then `-u` upgrade. **No staging/UAT DB for IG2** ⚠️ (blueprint §16 wants dev→CI→staging→prod).

## 3. Installed functional footprint on Mumtaz_IG2
- ✅ **Standard `account`** (invoicing, bills, payments, journals).
- ✅ **`base_accounting_kit`** (3rd-party) — adds `account.asset.*` (fixed assets) and other finance extras; emits two harmless field-label warnings.
- ✅ **`c2p_pk_vouchers`** (ours, v19.0.9) — PK Payment/Receipt/Journal/Payable/Receivable **vouchers** (branded print, whole-rupee, narration col, vendor name), **invoice knock-off**, **dual WHT** (income + sales) at bill via native taxes, **WHT certificate**, **intercompany transfer + mirror**, **interbank transfer**, **direct payment** (no vendor), **tax challan register**, **Cost Center / Job Code** analytic plans, **journal-voucher control**.
- ✅ **`mumtaz_financial_reports`** (ours, v19.0.2) — P&L, Balance Sheet, Trial Balance, General Ledger, Aged AR/AP; branded PDF + single-page Excel.
- ✅ **Chart of accounts** — full PK media-agency CoA (≈181 expense ledgers; trade discounts, BD/rebate pass-backs, content-trading COS, media monitoring, digital ads, payroll, FX, bank charges).
- ✅ **Masters seeded this engagement:** WHT payable ledgers (income 231001, sales 231101); **expense products** (one Service product per expense ledger, trimmed to ~102 billable); A.F.Ferguson bound to WHT.
- 🔎 **Not confirmed installed:** CRM, Sales (`sale_management`), Purchase, Inventory (`stock`), Projects/timesheets, HR/Payroll, e-invoicing (`mumtaz_einvoicing` exists in repo, likely **not** on IG2), dashboards. The §6 script settles this.

## 4. What is genuinely working (✅ demonstrated)
- Vendor **bill → pay (net) → knock-off**; **dual WHT at bill** (native tax, reduces payable, hits tax report).
- **Vouchers** post correct double-entry and print in PK format; **interbank** (Dr/Cr two banks) and **intercompany with mirror** across IG Square↔Mesh Media posted and verified.
- **Direct payment** (fines/penalties, no vendor) posts Dr account / Cr bank.
- **Financial statements** generate to PDF/Excel.

## 5. Gaps vs blueprint (fit-gap headlines — detail in `01-capability-matrix.md`)
| # | Gap | Blueprint ref | Severity |
|---|---|---|---|
| G-1 | **No approval/SoD on money-out.** Vouchers (incl. direct/intercompany/interbank) **post immediately**; no requester≠approver≠poster separation. | §8, §10.1, §3 | **High** |
| G-2 | **Security model unmapped** — roles, record rules, field-level (salary/bank/margin), cross-company leakage via `sudo()` in intercompany mirror not reviewed. | §10 | **High** |
| G-3 | **No staging/UAT environment** for IG2; changes upgrade straight on the live DB; no automated tests in the module. | §3.5, §16, §15 | **High** |
| G-4 | **Lead-to-cash spine status unknown** — is CRM→Quote→Sales Order→Customer Invoice used, or are AR invoices entered directly? | §6.1 | Med 🔎 |
| G-5 | **Receipt-side customer WHT** wiring (advance-tax receivables) pending; tax challans register built but not reconciled to a receivable. | §9 | Med |
| G-6 | **Fixed assets / depreciation** present via base_accounting_kit but register completeness (vehicles: MG, Haval, Sonata, bikes) unverified. | §5 FIN-04 | Med 🔎 |
| G-7 | **No executive dashboards / command center**; no budget vs actual. | §11.3, §5 BI-01 | Med |
| G-8 | **FBR digital invoicing** (PK) not enabled; statutory e-invoicing obligation unverified. | §13, §18 | Med 🔎 |
| G-9 | **Period locks / close policy / fiscal year** not confirmed; backdating controls unknown. | §9, ADR-011 | Med 🔎 |
| G-10 | **Voucher posting uses direct `account.move` line writes** rather than native payment/register in some paths — acceptable but must stay reconciled & server-validated; no unit tests guard it. | §4.2, §15 | Med |

## 6. Discovery script — run to turn 🔎 into ✅
Nothing below is coded against assumptions until this is run. It is **read-only** (no writes, no commit).

```bash
cat > /tmp/ig2_audit.py <<'PY'
def P(*a): print("AUDIT|", *a, flush=True)
IrM = env['ir.module.module']
inst = IrM.search([('state','=','installed')]).mapped('name')
P('odoo version:', env['ir.config_parameter'].sudo().get_param('base.version'))
P('installed module count:', len(inst))
for m in ['crm','sale_management','purchase','stock','account','account_accountant',
          'project','hr','hr_payroll','hr_expense','account_asset','base_accounting_kit',
          'mumtaz_einvoicing','c2p_pk_vouchers','mumtaz_financial_reports',
          'account_budget','spreadsheet_dashboard','documents']:
    P('  module', m, '=', 'INSTALLED' if m in inst else '-')
P('companies:', env['res.company'].search([]).mapped(lambda c:(c.id,c.name)))
P('users (active):', env['res.users'].search_count([('active','=',True)]))
for g in ['account.group_account_manager','account.group_account_user',
          'base.group_system','account.group_account_invoice']:
    try: P('  group', g, '=', len(env.ref(g).users))
    except Exception: P('  group', g, '= n/a')
AM = env['account.move']
for lbl,dom in [('customer invoices',[('move_type','=','out_invoice')]),
                ('vendor bills',[('move_type','=','in_invoice')]),
                ('journal entries',[('move_type','=','entry')]),
                ('posted moves',[('state','=','posted')])]:
    P('  moves', lbl, '=', AM.search_count(dom))
P('customers:', env['res.partner'].search_count([('customer_rank','>',0)]))
P('vendors:', env['res.partner'].search_count([('supplier_rank','>',0)]))
P('analytic plans:', env['account.analytic.plan'].search([]).mapped('name'))
try:
    P('fiscalyear lock:', env['res.company'].search([],limit=1).fiscalyear_lock_date,
      '| tax lock:', env['res.company'].search([],limit=1).tax_lock_date)
except Exception as e: P('lock dates n/a:', repr(e)[:60])
P('assets (base_accounting_kit):', env['account.asset'].search_count([]) if 'account.asset' in env else 'model n/a')
PY
sudo -u odoo /usr/bin/odoo shell -c /etc/odoo3.conf -d Mumtaz_IG2 --no-http < /tmp/ig2_audit.py 2>&1 | grep -E 'AUDIT\||Traceback|Error'
```

Paste the `AUDIT|` output; it fills §3 (installed modules), §5 G-4/G-6/G-9 (lead-to-cash, assets, locks), user/role counts and data volumes. Until then the 🔎 items stay unconfirmed and are **not** built against.
