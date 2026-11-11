# Plan v3 reconciliation

The owner supplied `plans/Jawhar_AI_First_Master_Product_Plan_v3.pdf` on
11 Nov 2026 as the proposed consolidated baseline. Per its §21, this page
records what was verified against it, which decisions were taken, and what
remains open. Precedence (plan §22): owner-approved decisions and verified
implementation override proposals.

## Baseline corrections (plan §3)

| Plan said | Verified on `main`, 11 Nov 2026 |
| --- | --- |
| Tests: 73 total incl. 54 Odoo | **19 pure-Python + 99 Odoo** before Slice 1; **+ 9 commitment + 5 API-sale tests** with it. Run by `scripts/jewel_ci.sh` and the GitHub gate on every PR |
| Maker/checker guard to be demonstrated | Held in `create`/`write` and the two actions, sudo included; `TestGoldRateApproval` (15 tests) |
| Counter / price-to-sale "in development" | **Price → quote → confirm → invoice → payment** runs from the product interface (Slice 1). The counter screen itself (POS, plan §27) is next |
| Role-based UI (plan §15) | `apps/jawhar-web` on `addons/mumtaz_jewellery_api`: see `JAWHAR_INTERFACE.md` |
| Infrastructure not inferable | Staging topology, deploy scripts and nginx are in `deploy/jewel-staging/`; demo at `jewel.mumtaz.digital` behind an allow-list/password, synthetic data only |

## Decisions taken with the owner, 11 Nov 2026

| Plan item | Decision | Where |
| --- | --- | --- |
| Architecture (§15, D8) | Odoo-native core; the product interface is standalone and talks only to the API door, which runs as the signed-in user | `JAWHAR_INTERFACE.md`, roadmap §4b |
| W02 self-approval | **Removed.** No setting waives the second approver; a one-person shop names a deputy | `mumtaz_jewellery` (`_check_can_decide`), signup page |
| Quote validity (§11 rate-to-quote) | Standard Odoo `quotation_validity_days` on the company; demo value **7**. A quote holds its rate until then (the rate lock); after, it must be renewed at today's approved rate before confirming | `mumtaz_jewellery_sale` (`action_renew_quote`, confirm guard) |
| Unique piece (§11 visit-to-sale, §20) | Confirm runs under a row lock on the piece and refuses: a piece on another live order, not on the shelf, out on approval, quantity ≠ 1 | `_jewellery_check_pieces_available` + 4 tests |
| Cost basis (§3 "do not derive accounting figures from the engine") | `stock.lot.jewellery_cost_value`, recorded, managers only; line margin = pre-tax price − cost, "unknown is not zero" | `mumtaz_jewellery`, `mumtaz_jewellery_sale` |
| Payment (§8) | Standard `account.payment.register` through the door; partial leaves the rest outstanding | API `/sales/invoices/<id>/payments` |
| Offline (§11, §17) | Online-only final commitment, as the plan recommends. No offline promise is made anywhere | — |
| Brand (§2) | Jawhar, the five agent names kept; "first UAE-made" **not** claimed anywhere on the site | site copy |

## Website audit W01–W16

| ID | Status | What changed |
| --- | --- | --- |
| W01 hero arithmetic | **Done** | One fixture: usual spend AED 7,500, suggested 22K bangle AED 6,404.88 (the demo's own 24.5 g piece at 245.80/g incl. VAT), "85% of typical" |
| W02 approval contradiction | **Done** | Self-approval option removed from product and setup page |
| W03 agent availability | **Done** | Intelligence page says what is usable today (Zayan as guide) vs specified |
| W04 feature status | Partial | Client 360 caption still describes prototype features; the live interface's Client 360 is the reference now. Full caption rewrite with the W09–W11 restructure |
| W05 compliance defaults | **Done** | Cash threshold has no default; wording says nothing here is validated law |
| W06 standard-Odoo claims | **Done** | "Installed and configured is not every feature proven" |
| W07 setup wording | **Done** | "Sample setup; creates nothing, charges nothing" |
| W08 audit scope | **Done** | "every agent call and every API call (who, what, when, outcome)" — which is what `jewellery.api.audit` logs |
| W09–W11 product-first, owner language, one story | Backlog | Landing restructure; do with the recorded demo video |
| W12 Arabic page | Backlog | The interface is bilingual; the landing page is not yet |
| W13 conversion / demo form | Backlog | Needs a human inbox and server-side validation; no form is live |
| W14 pricing | **Done** | Labelled concept preview; nothing purchasable |
| W15 trust | Open | No endorsements or certifications are claimed; readiness section to be written with pilot evidence |
| W16 naming | **Done** | Jawhar + five names, consistent across site and docs |

## Slice 3 (counter) — built 11 Nov 2026, plan §27

| Plan §27 element | Delivered |
| --- | --- |
| Selected piece / approved snapshot | Scan or type a serial/RFID; the engine's breakdown at the approved rate; dealer discount per line |
| Readiness checks | Live: approved rate, piece available (on shelf / on approval / sold / not in stock), client chosen, discount within the signed-in person's permission, old-gold intake confirmed and unused |
| Client / discretion | Tier, discreet billing, no-marketing, usual spend, relationship manager; a restricted client is visible only to those the record rule allows |
| Old gold | Separate intake panel: weight, karat, melt loss, buy-back → valued by the engine and confirmed; above the owner's threshold a second person approves; credited once, for exactly its value, as its own line |
| Commit action | **One call, one transaction**: confirm (every Slice 1 guard) → post the invoice → register the payment (full or deposit) → validate the delivery of *that* serial. Any refusal leaves nothing behind (test) |
| Failure state | The server's own sentence in place; nothing created |
| Receipt | Printable, with weights and the making breakdown per line |

Found while building it, all fixed with tests: standard reservation hands over *a* serial of the design, not the ordered one (two bangles on the shelf, the other one left); a standard-tier client with no purchase was invisible to the search, so a first sale could not be rung up; a staff discount had no ceiling.

Not built, on purpose: offline selling (online-only commitment, plan §11/§17) and the AML cash-threshold check (compliance values await the named finance manager, §17).

## Known limits after Slice 1

- A piece sold through *Quotes & orders* leaves stock when its delivery is
  validated (standard Odoo); the counter does that in its commit, the
  quotation path does not yet. Double-selling is prevented by the live-order
  check on both paths.
- The row lock is exercised logically by the tests (second order refused);
  a true two-connection race is not reproducible inside Odoo's test
  transaction and is left to a staging concurrency run.
- Tax on the invoice is the company default; VAT remains configuration for the
  named finance manager (plan §17).

## Next slices (plan §19)

2. Today + Layla draft tools, three-piece Private Tray, client link, viewing
   request, staff reservation — through the same door with autonomy levels.
3. Counter (POS, §27), Arabic native review, controlled messaging drafts.
Then 4 (pilot readiness), 5 (voice, portal), 6 (dealer, workshop, RFID).
