# Sales, CRM, POS and Inventory — solution design

Date: 2026-11-11. Standard-first, as the repo's working agreements require.
Module availability was read from the Odoo 19.0 Community source, not recalled.

**The short version: most of this is standard Odoo you configure.** Writing a
CRM or a POS for a jewellery chain would be the expensive way to get a worse
one. What is genuinely ours is narrow and specific, and it is listed below
with nothing padded into it.

---

## 1. Where the line falls

| Area | Standard Odoo gives you | What is genuinely ours |
| --- | --- | --- |
| **Sales** | Quotations, orders, delivery, invoicing, pricelists, taxes, multi-currency | A line priced from the **approved rate**, with the breakdown snapshotted and frozen on confirm |
| **CRM** | Leads, opportunities, stages, activities, predictive scoring (naive Bayes, ships in Community) | Stage *meaning* for jewellery; the tray as a lead; **explainable** next-piece ranking with reasons stored |
| **POS** | Offline operation, serial per line, shift close with cash variance, manager-only price control, barcode, cashier identity | Pricing a line **server-side** from the approved rate; a signed rate snapshot with an expiry for the offline session; old gold at the till |
| **Inventory** | Multi-warehouse, serial identity, quants, valuation, transfers, counts | Piece attributes and live price; **pieces on approval moving stock**; gram-level reconciliation |

Everything in the left column is installed and configured. Nothing in it is
built. Saying so is a feature of the product, not a weakness: the ladder is
standard config → views and `base_automation` → custom module, and Studio is
not available because `web_studio` is Enterprise.

---

## 2. Sales

**Done** — `mumtaz_jewellery_sale`, merged path, 13 tests.

A sale line carries `jewellery_lot_id` and is priced by
`stock.lot.get_price_breakdown()`, which calls the pure pricing library
against the rate a second person approved. The components are snapshotted
onto the line and frozen in `write()` once the order leaves draft, `sudo`
included.

Two rules that are easy to get wrong and are settled:

- **VAT belongs to Odoo.** The engine is called with `vat_rate=0` and
  `price_unit` carries the pre-tax subtotal. Taking tax from both charges it
  twice.
- **A dealer discount touches making only.** Never metal, never wastage.

### The price on the invoice

**Done too.** The snapshot travels onto `account.move.line` through
`_prepare_invoice_line` and freezes again once the move is posted.

Standard Odoo already carries the *money*, so the figure on the invoice was
always right. What it did not carry was the **derivation** of that figure, and
an invoice that cannot show where its number came from is no use in a client
query, a margin review or an audit.

Two findings from reading the Odoo 19 source, both of which changed the
design:

- **Odoo does not protect a posted line's price by default.**
  `account.move.line.write` blocks a posted line only through the fiscal lock
  date, the tax lock date, or an inalterable hash. A fresh database has none
  of the three, so the price on a posted jewellery invoice could simply be
  overwritten. For a line that carries a piece, that price is what a client
  agreed to pay for a specific object, so it is refused outright.
- **The invoice-line snapshot is `copy=True`, the sale-line snapshot is not.**
  On a quotation a copy is a new negotiation and must be priced afresh. An
  invoice is the opposite: a credit note is produced by *reversing* the move,
  and had the fields been `copy=False` the reversal would arrive with no rate,
  the posting guard would refuse it, and crediting a jewellery invoice would
  be impossible. The asymmetry is deliberate and has a test of its own.

The posting guard also catches a hand-made invoice line that carries a piece
but no rate — the same hole the order-confirmation guard closes, one document
further on.

**Done 11 Nov 2026 (Slice 1):** quote validity with the rate lock and
renewal, and the unique-piece guard under a row lock on confirm; both from
the product interface through the API door. See `PLAN_V3_RECONCILIATION.md`.

## 3. CRM

**Almost entirely standard, and the roadmap over-scopes it.** Slice 2B reads
as if the tray, viewing and reservation are a build. They are not:

| Jewellery concept | Standard Odoo object |
| --- | --- |
| A tray shared with a client | `crm.lead`, stages Draft → Shared → Viewing → Reserved → Won |
| A viewing in the diary | `mail.activity` on the lead |
| A reservation | `sale.order` in draft with the lot assigned |
| Odds of closing | `crm.lead.automated_probability` — naive Bayes, already in Community |

**What is ours:** the tokenised public link for the tray, and the ranking
that decides which pieces go in it.

The ranking already exists in `jewellery.offer` and the design principle is
worth defending: it is **deterministic, and it stores its reasons**. A score
with "matches preferred karat 22, within usual spend, suits upcoming wedding"
attached is something an associate can argue with. A model's opinion is not.

**Do not score Private and Royal clients.** Ranking a protocol client by
predicted probability is useless and, if ever seen, offensive. See
`PRIVATE_CLIENT_PROTOCOL.md`.

## 4. POS

**The offline work is already done — by Odoo.** `point_of_sale` ships a
service worker and a local IndexedDB store, so the till keeps selling when
the line drops and syncs after. This was verified against the source in
`POS_NATIVE_AUDIT.md` and it materially de-risks the slice: there is no
offline engine to write.

What is ours, and all of it is small:

1. **Price a line server-side from the approved rate.** Not by setting
   `price_type = manual` in JavaScript — a manual price is indistinguishable
   from a staff override, which destroys the control the whole product rests
   on.
2. **A signed rate snapshot with an explicit expiry on `pos.config` at
   session open.** Refuse to sell against an expired one. The expiry is a
   business decision and belongs in `ir.config_parameter`. This is the real
   offline risk, not connectivity.
3. **Old gold at the till**, with the second-approval threshold applied.
4. **Weight and making breakdown on the receipt.**

**Not available:** a connected scale. `iot` and `pos_iot` are Enterprise.
Weigh something on real hardware before promising it.

## 5. Inventory

**Serial identity, weights, karat, tag and live price are built and tested.**
Multi-warehouse, transfers and barcode counts are standard.

Two real gaps:

- **Pieces on approval do not move stock.** `action_return` and
  `action_sold` on `jewellery.approval.memo` write a state field and nothing
  else, so a piece sitting in a client's house still counts as on the shelf.
  Stock value overstates what you hold and a count will not reconcile.
  *This is what the accompanying change fixes.*
- **Gram-level reconciliation.** Odoo reconciles value and quantity, not fine
  weight across stores. Genuinely custom, and thin.

### The modelling decision for pieces on approval

A piece out on approval is **still yours**. It has not been sold, it is not a
delivery, and it must stay on your books and in your valuation. But it is not
on your shelf, and a shop count that expects to find it will not balance.

So it moves to an **internal location**, `Physical Locations / On approval`,
not to a customer location:

- ownership and valuation are unchanged, which is correct — it is your metal
- the shop location's on-hand drops, so the shelf count is right
- the approval location can be reported on separately, which is exactly what
  the owner view means by *"on your book, not on your shelf"*

Returning moves it back. Selling moves it from the approval location to
Customers, which is where a sale takes stock from anyway.

---

## 6. Where AI attaches

The agents do not get their own copy of any of this. They read it through the
tool registry, as the invoking user, so Odoo's record rules apply to them for
free — which is the only way *"an agent cannot see a client you cannot"* is
enforceable rather than promised.

| Agent | Reads | May never |
| --- | --- | --- |
| **Rayan** | Rate history, pricing engine, margins | Compute a price. He *calls* the engine; only a deterministic function can preserve rate, unit, purity, rule version and breakdown |
| **Layla** | Client book, purchase history, offers | Send. Outbound follows consent and approval policy; Private and Royal are never messaged automatically |
| **Noor** | Pieces, stones, certificates | Certify a stone. Image analysis is not laboratory verification |
| **Amara** | Accounting, margins, exposure | Post, approve or alter a transaction |
| **Zayan** | All of the above, consolidated | Override a financial control, a permission or a tenant boundary |

**No agent produces a number.** Every figure is read from the engine at the
approved rate. This is the one rule that cannot be configured away.

### The knowledge hub

Three distinct things, often conflated:

1. **Business data** — pieces, clients, rates. Lives in Odoo. Read through
   tools, never copied into a prompt wholesale.
2. **Domain knowledge** — karat and purity, stone grading, GCC tax treatment,
   what a *tola* is. Versioned documents, retrieved by relevance, cited in
   the answer.
3. **Tenant memory** — what this chain has learned: which pieces move in
   Ramadan, which objection lands, which supplier is late. Compounding, and
   **never shared between tenants**.

Retrieved content is **untrusted input**. It can inform an answer; it can
never change a permission. That needs a test, not a sentence.

---

## 7. Build order, and why

1. **Pieces on approval move stock** — closes a live defect in valuation
2. ~~**Price onto the invoice**~~ — done; the snapshot reaches
   `account.move.line` and freezes on posting
3. **POS: server-side pricing + rate snapshot with expiry** — the commercial
   unlock, and the offline risk that actually matters
4. **CRM: configure the stages, build only the link and the ranking**
5. **Gram reconciliation**
6. **Tool registry and the agent gateway** — after the data layer is honest,
   because an agent reading a wrong stock figure is worse than no agent

Everything above item 6 is ordinary Odoo work with tests. Nothing in it needs
an AI to be useful, which is the right shape: the intelligence is worth
having because the data underneath it is trustworthy, not instead of it.
