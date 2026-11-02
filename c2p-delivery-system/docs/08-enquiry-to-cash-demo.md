# Enquiry-to-Cash demonstration database

A repeatable way to stand up an Odoo database that walks the eleven-step
Enquiry-to-Cash process — the trading / distribution flow from customer RFQ
through costing, approval, quotation, purchase order, delivery with POD,
invoicing and collection, to the profitability review.

Source process chart: `docs/assets/enquiry-to-cash-flow.jpg`.

Script: `scripts/provision_demo_db.py`. One command creates the database,
installs the apps, applies the configuration, adds the automation and the
alerts, and seeds eight scenarios that between them hit every branch of the
chart — including the losing one.

## Running it

On the VPS, where Odoo lives:

```bash
cd /opt/mumtaz/c2p-delivery-system

# 1. See the plan without touching anything
python3 scripts/provision_demo_db.py C2P_DEMO_E2C --dry-run

# 2. Create and fill a fresh database
python3 scripts/provision_demo_db.py C2P_DEMO_E2C \
    --master-password "$ODOO_MASTER_PWD" --country AE

# 3. Or configure and seed a database that already exists
python3 scripts/provision_demo_db.py C2P_DEMO_E2C --no-create
```

Useful flags: `--only <phases>` re-runs part of it (`create, install, config,
fields, automation, alerts, seed, verify`), `--country` picks the fiscal
localization and chart of accounts, `--company` / `--currency` name the demo
entity, `--json` emits the verification counts for a health check.

Credentials follow `scripts/inspect_odoo_db.py`: `ODOO_URL` / `ODOO_USER` /
`ODOO_PASSWORD` from the environment or `delivery_api/.env`, with anything you
type on the command line winning. The database master password comes from
`--master-password` or `C2P_ODOO_MASTER_PWD` and is needed **only** to create
a database — it is never written to disk.

Everything is an `ensure`: re-running creates nothing it already made. The
second run reports `Records created: 0`.

## How the eleven steps are built

Standard-first, in the house ladder. No custom module is installed.

| # | Step | How it is delivered |
|---|------|--------------------|
| 1 | Customer Enquiry / RFQ | **Standard** — CRM pipeline, stages New → Assigned → Under Review → Estimation → Quotation → Won, sales team, source, deadline |
| 2 | Technical Review & Sourcing | **Standard** — vendor price lists (`product.supplierinfo`) with validity dates and lead times; Technical Review activity type |
| 3 | Costing & Margin Control | **Standard** — `sale_margin` puts cost and margin on every quotation line; `stock_landed_costs` for freight and duty into the product cost |
| 4 | Internal Approval | **Automation rule** — margin under 15% or a line discount over 10% moves the quote to Pending Approval and schedules a Margin Approval activity for the owner; a second rule stamps who approved and when |
| 5 | Customer Quotation | **Standard** — quotation with a 30-day validity; an automation starts the follow-up cadence when it is sent |
| 6 | Customer Decision | **Standard** — won on confirmation, lost with one of six lost reasons, or revised (the revision carries `x_revision_of` back to the original) |
| 7 | Customer PO & Sales Order | **Standard** — `client_order_ref` holds the customer PO; partner credit limits are switched on; an automation flags a confirmation with no PO reference |
| 8 | Procurement / Stock Allocation | **Standard** — purchase requisition, vendor PO, receipt into stock, multi-location allocation |
| 9 | Delivery & POD | **Standard** picking and partial delivery with backorder; **Studio-equivalent fields** for the POD the standard picking has no home for (`x_pod_received`, `x_pod_date`, `x_pod_signed_by`), driven by two automation rules |
| 10 | Invoicing & Collection | **Standard** — invoice from what was delivered, due dates from payment terms, payment registration, partial payment; a cron maintains the collection status |
| 11 | Profitability & Management Review | **Standard** — estimated vs actual margin from `sale_margin`, receivables and payables ageing; the alerts below are the exception reporting |

### The chart's statuses

Standard Odoo already carries most of them (`sale.order.state`,
`stock.picking.state`, `account.move.payment_state`). The sub-statuses it has
no field for are added as Studio-style `x_` fields and kept correct by the
automation rules, never by hand: `x_quote_status` (Draft / Pending Approval /
Approved / Submitted / Follow-up / Won / Lost / Expired), `x_po_status`,
`x_delivery_status`, `x_collection_status`.

### The nine alerts

The chart's Automated Alerts & Exceptions panel is nine Scheduled Actions,
all named `E2C Alert · …`: unassigned or overdue RFQs, expired supplier
prices, pending approvals ageing, overdue quotation follow-ups, credit limit
breaches, delayed deliveries and missing PODs, overdue invoices, cash forecast
shortfall, plus housekeeping that expires lapsed quotations.

## What is in the database to demonstrate

Eight scenarios, all dated relative to the day you run the script so the
overdue things are genuinely overdue:

- **DEMO-01 Al Mazroui** — the full cycle, steps 1 to 11: enquiry, approved
  quote, customer PO, supplier PO, receipt, delivery, signed POD, invoice,
  payment reconciled.
- **DEMO-02 Gulf Petrochem** — 60% delivered with a backorder open, POD on the
  first drop, invoice partly paid.
- **DEMO-03 Emirates Steel** — priced thin on purpose, so it is sitting in
  Pending Approval with the Margin Approval activity on it. This is the step 4
  demo.
- **DEMO-04 Desert Rock** — submitted and awaiting the customer decision, with
  the follow-up cadence running.
- **DEMO-05 Sharjah Water** — lost, reason recorded (the chart's Lost branch).
- **DEMO-06 Al Mazroui** — original quote cancelled and requoted after
  re-costing (the Revision branch).
- **DEMO-07 Desert Rock** — delivered, invoiced 62 days ago, unpaid: feeds the
  overdue-invoice and collection alerts.
- Four live enquiries at steps 1-2, one deliberately unassigned and past its
  required-by date so the first alert has something real to find.

Five role logins, password `demo1234` (change it with `--demo-user-password`):

| Login | Role in the chart |
|---|---|
| `layla.sales@demo.local` | Sales Team — steps 1, 5, 7 |
| `omar.estimation@demo.local` | Estimation Engineer — steps 2, 3, 8 |
| `rania.manager@demo.local` | Authorized Approver — step 4 |
| `tariq.warehouse@demo.local` | Warehouse / Logistics — step 9 |
| `hana.finance@demo.local` | Accounts / Finance — steps 10, 11 |

## Suggested demo path

1. Open the CRM pipeline — the enquiry stages are the chart's RFQ statuses.
2. Open **DEMO-03** as Rania: it is held at Pending Approval with the reason in
   the chatter. Approve it and watch the status and the approval stamp change.
3. Open **DEMO-02**: one delivery done, one backorder open — the chart's
   partial delivery branch — with the POD captured on the first drop.
4. Open **DEMO-01** end to end, then its invoice: paid and reconciled.
5. Open **DEMO-07**: overdue, with a Collection Call activity.
6. Settings → Technical → Scheduled Actions, filter `E2C` — the nine alerts.
   Run one by hand to show it raising activities.
7. Sales → Reporting → Margin for the step 11 view.

## Verification

The last phase counts what actually landed, step by step, and lists anything
it could not apply. Re-run it alone at any time:

```bash
python3 scripts/provision_demo_db.py C2P_DEMO_E2C --no-create --only verify
```

A count of zero against a step means that step did not build — read the
"Not applied" list underneath for the reason.

## Creating the database when `list_db = False`

A hardened deployment (ours included) switches off Odoo's database service,
so `--master-password` cannot work and `--no-create` is the only route. Two
things to get right first:

- **`dbfilter`**. If the config has `dbfilter = ^Mumtaz`, Odoo only serves
  databases whose name matches, so a demo called `C2P_DEMO_E2C` is invisible
  in the browser however well it is built. Name it `Mumtaz_Demo_E2C`.
- **The fiscal localization** has to be installed when the database is
  created, because step 10 has nowhere to post invoices without a chart of
  accounts.

```bash
sudo -u odoo createdb Mumtaz_Demo_E2C
sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf \
     -d Mumtaz_Demo_E2C -i base,l10n_ae --without-demo=all --stop-after-init

cd /opt/mumtaz/c2p-delivery-system
python3 scripts/provision_demo_db.py Mumtaz_Demo_E2C --no-create \
    --admin-user admin --admin-password admin
```

A freshly initialised database has `admin`/`admin`, which the script must be
told explicitly or it picks up the production credentials from
`delivery_api/.env`. Change that password before anyone outside the team sees
the database.

## Known limits

- **Odoo Community only.** Every module it installs ships with CE 19; nothing
  needs an Enterprise subscription. Approvals are automation rules and
  activities, not the Enterprise Approvals app.
- **Automation and alert code runs under `safe_eval`**, which rejects
  attribute assignment (`record.field = x` raises "forbidden opcode
  STORE_ATTR"). Every embedded block writes through `record.write({...})`
  instead. Lambdas and comprehensions are fine. If you add a rule, keep to
  that, and note `getattr` is not in the eval context either.
- **`stock_sms` arrives as a dependency** and puts an SMS confirmation wizard
  in front of every delivery validation. The script switches
  `stock_move_sms_validation` off and also answers the wizard if it appears.
- `res.config.settings` field names move between versions. Unknown settings
  are dropped and listed under "Not applied" rather than failing the run; if
  one you need is listed there, check its current name in this Odoo build.
  Known Odoo 19 removals: `po_lead`, `use_quotation_validity_days`.
- **Odoo 19 renamed `res.users.groups_id` to `group_ids`.** The script probes
  for whichever exists; the same trap applies to anything else you add.
