# Phase 2 — Odoo (reuse existing install)

We keep the working Odoo 19 at `erp.mumtaz.digital`. No reinstall.

## Catalogue → real addons
The dynamic `module_catalogue.odoo_module` values already map to addons that
exist, with two gaps now filled:

| Catalogue key | odoo_module | Status |
|---|---|---|
| einvoicing | `mumtaz_einvoicing` | exists (UAE/ZATCA/FBR services) |
| crm | `mumtaz_crm_starter` | **new (this phase)** |
| accounting | `account,account_accountant` | core |
| inventory | `stock,purchase` | core |
| hr_payroll | `hr,hr_payroll` | core |
| projects | `project` | core |
| manufacturing | `mrp` | core |
| marketplace | `mumtaz_marketplace` | exists |
| zaki | `mumtaz_zaki` | **new (this phase)** |
| vendor_portal | `mumtaz_vendor_portal` | exists |
| finance_sdk | `mumtaz_finance` | not built yet (Phase later) |

## New addons this phase
- **mumtaz_zaki** — `zaki.connector.get_snapshot()` returns the tenant's
  revenue/expenses/net/margin/cash/runway/AR-aging/payroll/pipeline as JSON.
  Optional modules (hr.payslip, crm.lead) are guarded. The ZAKI backend calls
  it via XML-RPC: `execute_kw(db, uid, pw, 'zaki.connector', 'get_snapshot', [])`.
- **mumtaz_crm_starter** — 7-stage pipeline (New Enquiry → Discovery → Proposal
  → Negotiation → Agreement → Won → Lost) + `x_lead_source`, `x_next_followup`.

## Install the two new addons (VPS)
```bash
cd /opt/custom_addons/Mumtaz && git pull origin main
# sync addons to Odoo's custom addons path (adjust path if different):
rsync -a addons/mumtaz_zaki addons/mumtaz_crm_starter /opt/custom_addons/Mumtaz/addons/ 2>/dev/null || true
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d <TENANT_DB> -i mumtaz_zaki,mumtaz_crm_starter --stop-after-init
sudo systemctl restart odoo
# verify the bridge:
#   python3 -c "import xmlrpc.client as x; ... call zaki.connector.get_snapshot"
```

## db_filter isolation — DO NOT change the live conf blindly
The spec sets `db_filter = ^%d$` (serve only the DB whose name matches the
host). On the current **single** `erp.mumtaz.digital` host that serves several
tenant DBs, setting `^%d$` would make the host match a DB literally named
`erp.mumtaz.digital` → **locks everyone out**. Two safe routes:

1. **Recommended now:** keep `dbfilter` permissive and rely on the control
   panel's SSO `odoo-link` (Phase 4), which opens the ERP with the tenant's
   `db=` explicitly and per-DB credentials. Isolation is already at the DB level
   (each tenant = its own PostgreSQL DB).
2. **Per-subdomain isolation (later):** give each tenant `{slug}.erp.mumtaz.digital`,
   DNS + nginx pass `Host`, set `db_filter = ^%h$` (or name DBs to match host).
   Roll out per tenant; test on one before global.

Tenant isolation today = one PostgreSQL DB per tenant + scoped SSO. The db_filter
hardening is an enhancement, not a prerequisite.
