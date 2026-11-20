# Pharma DEMO — presenter script (all data fictional)

Environment: https://pharma.mumtaz.digital · Odoo 19 Community · database `mumtaz_pharma`,
`pharma.mode = demo`, neutralized (no e-mail, no payment provider). Everything shown is
seeded by `pharma_demo_data` + `pharma_website_demo` and flagged **DEMO**. Re-seeding is
idempotent (`-u pharma_demo_data` adds nothing twice).

## Where things are: one app per area

The Pharma platform is not one big menu. Each area is its own app in the app switcher (top-left grid), with its own icon and menus,
and each is provided by the module that owns it. A user only sees the apps their role allows.

| App | Menus | Provided by |
| --- | --- | --- |
| **Tax Centre** | Blocked (Unresolved), Tax Events, SKU Classification Register, Tax Rules | `pharma_pk_tax_core` |
| **Reconciliation** | Exception Queue, Reconciliation Runs | `pharma_reconciliation_hub` |
| **Distribution Partner** | Stock Roll-forward, Commercial Model (A/B/C) (Finance only) | `pharma_reconciliation_hub` |
| **Courier COD** | Shipments, COD Ageing, Remittances, Statement Uploads, Configuration › Couriers (Administrator) | `pharma_courier_cod` |
| **Pharma Admin** | Source Events (Administrator only) | `pharma_core` |

The standard Odoo apps (Sales, Website, Inventory, Purchase, Manufacturing, Accounting) sit beside them. After an upgrade, hard-refresh the browser to see the new switcher.

## Who logs in

| Login | Role | Use it to show |
| --- | --- | --- |
| owner's admin login | every Pharma role (demo convenience) | overview, "second approver" in maker-checker |
| `pharma.ops` | Pharma: Operations User | read-only views, cannot run matching or approve |
| `pharma.maker` | Pharma: Administrator (+ product manager) | drafts tax rules, proposes SKU classifications, cannot approve |
| `pharma.approver` | Pharma: Tax Approver | approves rules and classifications, refuses its own drafts |
| `pharma.finance` | Pharma: Finance Controller | runs matching, owns exceptions, proposes closure; needs a second controller to approve |

Passwords for the four demo users are set on the server with `stage.sh demo-passwords`; they are
not in this repository.

## Public website (no login)

| # | Do | Expect |
| --- | --- | --- |
| W1 | Open https://pharma.mumtaz.digital | Health-and-wellness home at `/pharma`: terracotta **DEMO ENVIRONMENT** ribbon above the header, logo, hero *Everyday wellness, kept honest.* with three product cards, trust strip, five featured products, three control cards, "A demonstration, clearly marked" |
| W2 | Click **Browse the shop** (`/shop`) | 5 products A to E in two categories (Infusions, Blends & Mixes), pastel pack art stamped DEMO, soft cards that lift on hover, ribbon still visible |
| W3 | Add *Green Leaf Infusion (DEMO)* to the cart, proceed to checkout | Address step works; payment step shows **no provider** (database is neutralized) — say so, this is by design |
| W4 | Add *Rose Petal Tea (DEMO)* | It can be carted; the control bites at order confirmation in the back office (T4 below), never silently at checkout |

## Tax Centre (app: **Tax Centre**)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| T1 | any | **Tax Rules** | DEMO-RULE-0 (8 %, 2025, end-dated), -1 (10 %), -2 (2 %) approved · -3 draft · -4 draft · -5/-6 approved and overlapping · -7 superseded. DEMO column ticked everywhere |
| T2 | `pharma.maker` | open DEMO-RULE-3 › **Approve** | refused: "Only a Pharma Tax Approver can approve" |
| T3 | `pharma.approver` | DEMO-RULE-4 › **Approve** | refused: legal and evidence references required (evidence is empty) |
| T3b | `pharma.approver` | DEMO-RULE-3 › **Approve** | approved, approver and timestamp recorded; maker ≠ approver |
| T4 | admin | **Sales › Quotations › DEMO-SO-BLOCKED › Confirm** | blocked: "no approved tax classification for Rose Petal Tea (DEMO)" |
| T4b | admin | Quotation DEMO-SO-OK (already confirmed) | confirmed normally; approved SKU |
| T5 | admin | **Accounting › Customer Invoices › DEMO-INV-BLOCKED › Confirm** | blocked by the same gate; DEMO-INV-OK is posted |
| T6 | `pharma.approver` | **SKU Classification Register** › DEMO-SKU-E (Warm Spice Mix) › **Approve classification** | approved; proposed by `pharma.maker`, approved by `pharma.approver` |
| T6b | `pharma.maker` | same button on a product he proposed | refused: maker-checker |
| T7 | any | **Blocked (Unresolved)** | DEMO-SKU-C (Rose Petal Tea) (pending) listed; DEMO-SKU-E (Warm Spice Mix) disappears once T6 is done |
| T8 | any | **Tax Events** | 8 events; DEMO-O-1004 has an *original* and a *reversal* (cancelled prepaid order). Open one › try to edit | refused: immutable, "Use Reverse" |
| T9 | admin | Settings › Technical › System Parameters › `pharma.mode` = `production` (then back to `demo`) | with `production`, resolving a DEMO rule returns *needs_approval: DEMO-only and refused in production*; proven by the test suite and `stage.sh smoke` without touching the database |
| T10 | any | Product D "ambiguous rules" | two approved rules overlap for its class: any posting resolves **blocked: ambiguous**; nothing is guessed |

## Reconciliation (app: **Reconciliation**)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| R1 | any | **Reconciliation Runs** | R03 batch 2 *clean* = Matched, 0 exceptions (gross 50,000 − fee 2,500 = 47,500 received) |
| R2 | any | R03 batch 1 | Partial; variance **−2,000** (106,000 − 5,000 fees = 101,000 expected vs 99,000); exception *pending approval* |
| R3 | any | R04 gateway payout | payout 20,000 matched one-to-many; bank credit 3,500 with no reference = **Unidentified**, state *investigating*, owner `pharma.finance` |
| R4 | any | R05 bank vs ledger | LEDGER-001 exact match · LEDGER-002 reference matches, amount differs (7,000 vs 7,200) = exception, *closed* · LEDGER-003/004 same amount, same window = **Ambiguous**, open · LEDGER-005 matched **amount_date_LOW_CONFIDENCE** |
| R5 | `pharma.ops` | any run › **Run matching** | refused: "Only a Finance Controller can run matching" |
| R6 | `pharma.finance` | **Exception Queue** › the *pending approval* COD variance › **Approve closure** | refused: maker-checker, proposer cannot approve |
| R6b | admin (second controller) | same › **Approve closure** | closed; `proposed_by` and `approved_by` differ |
| R7 | `pharma.finance` | an *open* exception › **Propose closure** without owner / note | refused: "Assign an owner", then "A resolution and a note are required" |

## Distribution Partner (app: **Distribution Partner**)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| P1 | any | **Stock Roll-forward** | DEMO-LOT-01 variance 0 · DEMO-LOT-07 **−2** · DEMO-LOT-11 0 · DEMO-LOT-02 **+3**; one open exception per variance in the Exception Queue, nothing written off |
| P2 | `pharma.finance` | **Commercial Model (A/B/C)** | scenario B chosen, contract reference empty, no sign-offs → *complete* unticked. Custody moves are recorded; revenue is **BLOCKED awaiting sign-off** |
| P3 | `pharma.ops` | **Commercial Model** menu | not visible (Finance only) |

## Courier COD ledger (app: **Courier COD**, Pakistan cash on delivery)

Seeded by `pharma_courier_cod_demo` with two fictional couriers, **Courier A (DEMO)** (14-day remittance cycle) and
**Courier B (DEMO)** (7-day cycle). Three amounts are tracked per parcel: **declared** (what the shop asked the courier
to collect), **collected** (what the courier says it took from the customer) and **remitted** (what the courier accounted
for on a remittance slip). A shortfall between any two is its own finding, never absorbed.

| # | As | Do | Expect |
| --- | --- | --- | --- |
| C1 | `pharma.finance` | **Shipments** (list) | 19 parcels across both couriers; COD status, days outstanding, ageing bucket and **Overdue** on each; DEMO column ticked |
| C2 | any | **COD Ageing** (pivot) | parcels awaiting remittance split into 0-7, 8-15, 16-30 and 31+ days by courier. Ageing runs from the **delivery date**, not the booking date. Use the **Refresh ageing** action (list **Action** menu, or the button on a parcel) first if this database is more than a few days old: ageing moves with the calendar |
| C3 | `pharma.finance` | **Remittances** › `DEMO-SL-A-1001` | clean batch: collected = declared = remitted gross, bank = gross minus itemised deductions (freight, COD fee, sales tax on services); reconciled run is **matched**, no exceptions |
| C4 | `pharma.finance` | `DEMO-SL-A-1002` › the reconciliation-run smart button | partial, with three findings: `DEMO-A-0004` customer paid less than declared (**collection**), `DEMO-A-0005` courier remitted less than it collected (**remittance**), and the bank deposit is 400 short of the slip |
| C5 | `pharma.finance` | `DEMO-SL-B-1001` | deductions 800 against an authorized 500: a **deduction** finding for the 300 above what was agreed (the unexplained *Other Deductions*) |
| C6 | any | **Shipments** filtered Overdue | `DEMO-A-0103` (20 days), `DEMO-A-0104` (45 days) and `DEMO-B-0102` (9 days, over Courier B's 7-day cycle) are overdue, and so are still-unremitted parcels in general; `DEMO-A-0102` at 10 days is not, because Courier A's cycle is 14 |
| C6b | any | **Exception Queue** › category *Remittance overdue* | six findings on staging: the three above, plus `DEMO-A-0001` to `-0003`. Those three were delivered 24 days ago and flagged overdue when the delivery report was loaded; the slip that settled them arrived later, so they are remitted now but the earlier finding stays open until someone closes it. Say so: a finding is a record of what was true when it was raised |
| C7 | any | `DEMO-B-0201` | state *Returned* but COD was collected: a **returned COD** finding, because the customer's money is with the courier |
| C8 | any | `DEMO-A-0301` | the courier reports an order reference the shop has no sale order for: an **intake** finding |
| C9 | `pharma.finance` | **Statement Uploads** › the one in *Draft* with 3 bad rows | each row names its problem (no tracking number, delivered with no date, negative amount); **Build documents** stays refused until fixed. Nothing from it reached the ledger |
| C10 | `pharma.finance` | **Statement Uploads** › the *Built* one | 8 parcels created from one delivery report; each row is archived unchanged in **Source Events** |
| C11 | `pharma.ops` | open **Remittances** or **Statement Uploads**; try *Reconcile* or *Build documents* | read-only for Operations; matching and building are Finance Controller actions |

### Settlement accounting (`pharma_courier_cod_accounting`, see COURIER_COD_ACCOUNTING.md)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| C12 | admin (an accountant) | **Remittances** › `DEMO-SL-A-1001` › **Journal Entry** | a *draft* entry already exists: credit to the courier clearing account for the gross, debits to bank, freight, COD fee and withholding sales tax. Balanced, nothing posted |
| C13 | `pharma.finance` | `DEMO-SL-A-1002` › **Create journal entry** | draft created even though this user has no Accounting rights; the 400 bank shortfall is its own line on the *difference* account |
| C14 | `pharma.finance` | same button again, or on `DEMO-SL-A-1003` before it is reconciled | refused: "already has journal entry" / "must be posted and reconciled first". Only admin can open the entry itself |

| C15 | admin | **Shipments** › `DEMO-A-0001` › **Open collection entry** | draft entry from slice 1c: debit courier clearing 2,500, credit the customer's receivable with the customer on the line. Same for `-0002` (4,200) and `-0003` (1,800). Together they cancel the settlement entry of C12 on the clearing account: the clearing balance for that batch is zero |
| C16 | `pharma.finance` | **Shipments** › `DEMO-A-0004` (delivered, collected 2,700) › **Create collection entry** | a draft is created for 2,700, not the declared 3,000. Try it on `DEMO-A-0302` (in transit) or `DEMO-B-0201` (returned): refused with the reason. Select several shipments in the list, **Action › Create collection entries**: all or nothing |

| C17 | admin, then `pharma.finance` | As admin post `DEMO-A-0001`'s collection entry (Accounting). As `pharma.finance`: **Reverse collection entry**, enter a reason | wizard creates a *draft* reversal, the shipment shows *Reversal drafted* and **Create collection entry** stays hidden. Post the reversal as admin: the shipment shows *Reversed*, the button returns, and a corrected entry can be created; the old one is listed under *Superseded Entries* |

### Live upload (the part to do in front of the audience)

Sample files are in the module at `pharma_courier_cod_demo/static/samples/`. Open them at
`https://pharma.mumtaz.digital/pharma_courier_cod_demo/static/samples/<file>` or take them from the repository; headings are the exact field labels, so Odoo's import screen maps every column by itself.

1. `pharma.finance` › **Statement Uploads** › New: Courier A, type *Shipment / delivery report* › Save › **Upload file**
   › choose `courier_a_delivery_report.csv` › **Test** then **Import**. Six staging rows appear.
2. **Validate rows**. The file is clean, so the statement turns *Validated*. **Build documents** creates six parcels;
   `DEMO-A-0406` has no sale order and `DEMO-A-0405` came back with COD collected, so two findings appear at once.
3. New statement: Courier A, type *COD remittance slip*, slip reference `DEMO-SL-A-1003`, a date, **Received at Bank
   6660** › **Upload file** › `courier_a_remittance_slip.csv` › **Validate rows** › **Build documents**. A *draft* remittance
   with three lines appears. Nothing is counted as remitted until it is posted.
4. Open the remittance › **Post** › **Reconcile against the bank**. The run matches (2320 + 3120 + 1220 = 6660) and the three
   parcels move to *Remitted*.
5. Run step 3 again with bank 6460: the 200 difference is a finding. Run it a third time with the same slip reference: refused,
   "already has remittance". Uploading the same delivery report twice updates the same parcels and never blanks a field the
   second file left empty.

## Source events (app: **Pharma Admin › Source Events**, Pharma Administrator)

| # | Expect |
| --- | --- |
| S1 | DEMO-O-1007 appears once although it was ingested twice (replay ignored) |
| S2 | DEMO-O-1008 is in state **Conflict**: same id, different payload; the first payload is kept |
| S3 | Open any event, try to edit or delete | refused: immutable |

## Back-office signs that this is a demo

Red **neutralized** banner on every back-office page (standard Odoo), company *Pharma Demo Co*,
DEMO column on every Pharma list, "(fictional)" in every product name, DEMO ribbon on every public page. The public site carries no health claims anywhere: every product page says so.

## Mapping to automated tests (`--test-tags pharma`)

pharma_pk_tax_core (T1–T10): 18 tests · pharma_reconciliation_hub (R1–R7, P1–P3, S1–S3): 16 tests ·
pharma_demo_data (every row above exists after install, seeding is idempotent, products are shop-ready): 13 tests · pharma_website_demo (home page, shop, product page, ribbon, stylesheet bundle, no health claims, seeding): 7 tests. pharma_courier_cod (shipment states and ageing, exceptions and their dedupe, remittance locking and deductions, statement validation / build / archiving, end-to-end flow): 67 tests · pharma_courier_cod_accounting (settlement entry: balanced draft, every deduction on its own account, bank difference both ways, guards; collection entry: amount collected, customer on the receivable line, refusal reasons, all-or-nothing batch, clearing nets to zero with the settlement): 29 test methods · pharma_courier_cod_demo (every scenario above exists, seeding is idempotent, sample files match the staging labels, accounts configured, one draft entry): 12 tests. Total 54 for the first five modules; the whole suite on staging is 176 plus the 13 tests added by slice 1c.
