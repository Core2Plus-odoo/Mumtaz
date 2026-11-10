# What Odoo 19 Community's POS already does, and what Jewel still has to build

Date: 2026-11-10. Read against the Odoo 19.0 source in this session
(`addons/point_of_sale` and the 40 `pos_*` modules beside it), not from
memory. Standard-first: nothing below should be rebuilt if the standard path
already covers it (`docs/mumtaz-jewel/CLAUDE.md`).

**Caveat on method.** This is a source read, not a running POS. Nothing here
has been installed or exercised on a database. Each "native" claim names the
file it came from so it can be checked; each one still needs proving in the
Slice 2 spike before it is treated as done.

## Already native — do not rebuild

| Capability | Where it lives | What it means for Jewel |
| --- | --- | --- |
| **Offline operation** | `static/src/app/service_worker.js` caches assets; `services/data_service.js` keeps the session in **IndexedDB**, listens for the browser `offline` event, runs its own connectivity check, and asks the browser for persistent storage. There is a `sync_popup` and a `reset_local_data` recovery path | The offline counter is largely **standard**, not a from-scratch build. This is the single biggest finding |
| **Serial number per sold line** | `pos.pack.operation.lot` model, `pack_lot_ids` on `pos.order.line`, `select_lot_popup` UI, `picking_type_id` on `pos.config` | Each Jewel piece is a serial-tracked `stock.lot`. The POS already records **which** piece left |
| **Shift open and close with cash variance** | `pos_session.py`: `cash_register_balance_start` / `_end` / `_end_real`, `cash_register_difference`, plus `opening_control_popup`, `closing_popup`, `money_details_popup` | Shift close with a counted-versus-expected difference is native |
| **Price changes restricted to managers** | `pos_config.restrict_price_control`, `group_pos_manager`; lines carry `price_type` of `original` or `manual` | The hook for "staff cannot type over the engine's figure" exists, and a manual override is already distinguishable |
| **Discounts** | `pos_discount` (simple), `pos_loyalty` → `loyalty` (programmes, promotions) | Dealer and staff discount mechanics exist; the Jewel rule (discount on making only, never metal) is the part to add |
| **Refunds and returns** | `is_refund` on `pos.order`, sign handling in `_prepare_invoice_line` | Native |
| **Multi-store** | One `pos.config` per shop, each with its own `picking_type_id` → warehouse, and `company_id` | Per-store tills map onto standard config |
| **Barcode / tag scanning** | `point_of_sale` depends on `barcodes`; `barcode_rule.py` | Tag scan is native; RFID is a hardware question, not a software one |
| **Who served the client** | `pos_hr` links cashiers to HR employees | The "Nadia M., 45 min" line on a visit has a native source |
| **Repairs taken at the counter** | `pos_repair` ships in Community | Jewellery repair intake is partly native — worth a look before Slice 10 |
| **Sell against a quotation** | `pos_sale`, `pos_sale_margin` | A tray quoted in the back office can be settled at the till |
| **Receipt by SMS** | `pos_sms` | Bilingual receipt delivery has a starting point |

## Gaps Jewel has to build

| Gap | Why standard does not cover it |
| --- | --- |
| **Price from the approved gold rate** | POS prices from the pricelist and `lst_price`. A Jewel piece is priced from net weight × karat × the approved rate, plus wastage, making, stones and VAT. The line price has to be computed by the engine and pushed into the order line, not typed |
| **The rate inside an offline session** | The POS loads its data at session open. Which rate an offline sale used, how long that snapshot stays valid, and what happens when it goes stale are all Jewel policy. This is the real offline risk — not the offline mechanism itself |
| **Old gold taken in exchange at the till** | There is no native concept of buying metal back from a customer mid-sale. Needs a line type or a linked `jewellery.old.gold` record, with the second-person approval above the threshold |
| **The same piece sold twice offline** | Two terminals offline both hold the same serial as in stock. The POS syncs orders, but resolving a double-sold serial into one sale and one visible conflict is Jewel's to write |
| **Weight and the making breakdown on screen and on the receipt** | `product.template.to_weight` is for weighing produce against a UoM, not for a piece's own gross, stone and net metal weights |
| **Discount that never touches metal** | `pos_discount` discounts the line. Jewel's rule applies to the making charge only |
| **AML threshold at the moment of payment** | Nothing native watches a client's year-to-date cash against a configured limit |
| **Client context at the till** | POS shows a partner, not a tier, an AML status, a no-marketing flag or what the client already owns |

## Hardware: the one thing to verify before promising it

`point_of_sale` depends on `iot_base`, which **is** in this Community tree, and
`product.template` carries `to_weight` ("To Weigh With Scale"). But **`pos_iot`
is not among the 40 `pos_*` modules in Community** — the list is in this
session's notes and runs from `pos_account_tax_python` to `pos_viva_com` with
no `pos_iot`.

So: the hooks for a scale are visible, the driver layer may not be. **A
connected scale at the counter is not yet proven available in Community** and
must not be promised to a customer until someone installs it and weighs
something. For jewellery this matters more than for most retail.

## What this changes in the roadmap

Slice 2 treats the offline counter as the headline risk and opens with a
week-one spike to prove feasibility. On this reading the offline *mechanism*
is standard and already shipped — service worker, IndexedDB, connectivity
detection, sync. The spike should therefore stop asking "can Odoo go offline"
and start asking the questions that are actually Jewel's:

1. Which rate does an offline sale price against, and when does that snapshot
   expire?
2. What happens when the same serial is sold on two offline terminals?
3. Can the engine's price be pushed onto a POS line cleanly, and does it
   survive a sync?

That is a narrower and more honest spike, and it is a material de-risking of
the slice rather than a cosmetic one.

## Not checked

Receipt layout and bilingual or right-to-left printing; the Odoo 19 POS
self-order flow; payment terminal modules (many ship, all region-specific);
how `pos_repair` actually behaves; and whether any of the above changed
between 19.0 at this commit and the release the customer would run.
