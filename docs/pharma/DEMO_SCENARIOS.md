# Pharma DEMO — presenter script (all data fictional)

Environment: https://pharma.mumtaz.digital · Odoo 19 Community · database `mumtaz_pharma`,
`pharma.mode = demo`, neutralized (no e-mail, no payment provider). Everything shown is
seeded by `pharma_demo_data` + `pharma_website_demo` and flagged **DEMO**. Re-seeding is
idempotent (`-u pharma_demo_data` adds nothing twice).

## Who logs in

| Login | Role | Use it to show |
| --- | --- | --- |
| owner's admin login | every Pharma role (demo convenience) | overview, "second approver" in maker-checker |
| `demo_ops` | Pharma: Operations User | read-only views, cannot run matching or approve |
| `demo_maker` | Pharma: Administrator (+ product manager) | drafts tax rules, proposes SKU classifications, cannot approve |
| `demo_approver` | Pharma: Tax Approver | approves rules and classifications, refuses its own drafts |
| `demo_finance` | Pharma: Finance Controller | runs matching, owns exceptions, proposes closure; needs a second controller to approve |

Passwords for the four demo users are set on the server with `stage.sh demo-passwords`; they are
not in this repository.

## Public website (no login)

| # | Do | Expect |
| --- | --- | --- |
| W1 | Open https://pharma.mumtaz.digital | Demo home at `/pharma`: red **DEMO ENVIRONMENT** ribbon above the header, three capability cards, "About this environment" |
| W2 | Click **Browse DEMO products** (`/shop`) | 5 products in two categories (DEMO Wellness, DEMO Nutrition), each image stamped DEMO, ribbon still visible |
| W3 | Add *DEMO Wellness Product A* to the cart, proceed to checkout | Address step works; payment step shows **no provider** (database is neutralized) — say so, this is by design |
| W4 | Add *DEMO Wellness Product C (tax pending)* | It can be carted; the control bites at order confirmation in the back office (T4 below), never silently at checkout |

## Tax Centre (`Pharma › Tax Centre`)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| T1 | any | **Tax Rules** | DEMO-RULE-0 (8 %, 2025, end-dated), -1 (10 %), -2 (2 %) approved · -3 draft · -4 draft · -5/-6 approved and overlapping · -7 superseded. DEMO column ticked everywhere |
| T2 | `demo_maker` | open DEMO-RULE-3 › **Approve** | refused: "Only a Pharma Tax Approver can approve" |
| T3 | `demo_approver` | DEMO-RULE-4 › **Approve** | refused: legal and evidence references required (evidence is empty) |
| T3b | `demo_approver` | DEMO-RULE-3 › **Approve** | approved, approver and timestamp recorded; maker ≠ approver |
| T4 | admin | **Sales › Quotations › DEMO-SO-BLOCKED › Confirm** | blocked: "no approved tax classification for DEMO Wellness Product C" |
| T4b | admin | Quotation DEMO-SO-OK (already confirmed) | confirmed normally; approved SKU |
| T5 | admin | **Accounting › Customer Invoices › DEMO-INV-BLOCKED › Confirm** | blocked by the same gate; DEMO-INV-OK is posted |
| T6 | `demo_approver` | **SKU Classification Register** › DEMO-SKU-E › **Approve classification** | approved; proposed by `demo_maker`, approved by `demo_approver` |
| T6b | `demo_maker` | same button on a product he proposed | refused: maker-checker |
| T7 | any | **Blocked (Unresolved)** | DEMO-SKU-C (pending) listed; DEMO-SKU-E disappears once T6 is done |
| T8 | any | **Tax Events** | 8 events; DEMO-O-1004 has an *original* and a *reversal* (cancelled prepaid order). Open one › try to edit | refused: immutable, "Use Reverse" |
| T9 | admin | Settings › Technical › System Parameters › `pharma.mode` = `production` (then back to `demo`) | with `production`, resolving a DEMO rule returns *needs_approval: DEMO-only and refused in production*; proven by the test suite and `stage.sh smoke` without touching the database |
| T10 | any | Product D "ambiguous rules" | two approved rules overlap for its class: any posting resolves **blocked: ambiguous**; nothing is guessed |

## Reconciliation (`Pharma › Reconciliation`)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| R1 | any | **Reconciliation Runs** | R03 batch 2 *clean* = Matched, 0 exceptions (gross 50,000 − fee 2,500 = 47,500 received) |
| R2 | any | R03 batch 1 | Partial; variance **−2,000** (106,000 − 5,000 fees = 101,000 expected vs 99,000); exception *pending approval* |
| R3 | any | R04 gateway payout | payout 20,000 matched one-to-many; bank credit 3,500 with no reference = **Unidentified**, state *investigating*, owner `demo_finance` |
| R4 | any | R05 bank vs ledger | LEDGER-001 exact match · LEDGER-002 reference matches, amount differs (7,000 vs 7,200) = exception, *closed* · LEDGER-003/004 same amount, same window = **Ambiguous**, open · LEDGER-005 matched **amount_date_LOW_CONFIDENCE** |
| R5 | `demo_ops` | any run › **Run matching** | refused: "Only a Finance Controller can run matching" |
| R6 | `demo_finance` | **Exception Queue** › the *pending approval* COD variance › **Approve closure** | refused: maker-checker, proposer cannot approve |
| R6b | admin (second controller) | same › **Approve closure** | closed; `proposed_by` and `approved_by` differ |
| R7 | `demo_finance` | an *open* exception › **Propose closure** without owner / note | refused: "Assign an owner", then "A resolution and a note are required" |

## Distribution Partner (`Pharma › Distribution Partner`)

| # | As | Do | Expect |
| --- | --- | --- | --- |
| P1 | any | **Stock Roll-forward** | DEMO-LOT-01 variance 0 · DEMO-LOT-07 **−2** · DEMO-LOT-11 0 · DEMO-LOT-02 **+3**; one open exception per variance in the Exception Queue, nothing written off |
| P2 | `demo_finance` | **Commercial Model (A/B/C)** | scenario B chosen, contract reference empty, no sign-offs → *complete* unticked. Custody moves are recorded; revenue is **BLOCKED awaiting sign-off** |
| P3 | `demo_ops` | **Commercial Model** menu | not visible (Finance only) |

## Source events (`Pharma › Configuration › Source Events`, Pharma Administrator)

| # | Expect |
| --- | --- |
| S1 | DEMO-O-1007 appears once although it was ingested twice (replay ignored) |
| S2 | DEMO-O-1008 is in state **Conflict**: same id, different payload; the first payload is kept |
| S3 | Open any event, try to edit or delete | refused: immutable |

## Back-office signs that this is a demo

Red **neutralized** banner on every back-office page (standard Odoo), company *Pharma Demo Co*,
DEMO column on every Pharma list, "(fictional)" in every product name, DEMO ribbon on every public page.

## Mapping to automated tests (`--test-tags pharma`)

pharma_pk_tax_core (T1–T10): 18 tests · pharma_reconciliation_hub (R1–R7, P1–P3, S1–S3): 16 tests ·
pharma_demo_data (every row above exists after install, seeding is idempotent): 12 tests.
