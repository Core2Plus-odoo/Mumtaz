# Functional review of the three addons

Date: 2026-11-10. A read of every model, action and cron in
`mumtaz_jewellery`, `_vip` and `_owner`, against what the product claims.
Source read, not a running system; nothing here was changed except the
landing-page wording in finding 1.

## The functional surface, as built

| Model | Actions | Scheduled |
| --- | --- | --- |
| `jewellery.gold.rate` | approve, reject | — |
| `jewellery.old.gold` | confirm, approve, issue to production, cancel | — |
| `jewellery.approval.memo` | return, sold | reminder before the return date |
| `jewellery.occasion` | — | prepare drafts before the date |
| `jewellery.offer.suggestion` | accept, dismiss | — |
| `jewellery.owner.card` | open, dismiss, refresh | hourly refresh |
| `jewellery.vip.access.log` | read-only | — |
| extends `product.template`, `stock.lot`, `res.partner` | — | — |

Menus: Gold Rates, Pieces, Products, Old Gold Exchange, Command Centre, VIP
Clients, Pieces on Approval, VIP Access Log.

## Findings

### 1. "Every view is logged" was overstated — page corrected

`res.partner.web_read` is the only override that writes to
`jewellery.vip.access.log`. In the Odoo web client that fires when someone
**opens a record**. It does **not** fire for:

- a list or kanban view (`web_search_read`),
- `read()` or `search_read()` over RPC or XML-RPC,
- an export,
- a report.

So a user who can see a Private client can read their name, tier,
relationship manager and lifetime value in a list, or export them, leaving no
line in the access log. The record rule still limits **who** can see them; the
gap is in the **logging**, not the access.

The landing page said "every single view is written to a log". That claim is
now "opening one writes a line to an access log with who and when", which is
what the code does. **No code was changed**: widening the log to cover
`web_search_read` and exports is a behaviour change that needs a decision, and
it has a cost — a list of 200 clients would write 200 rows per refresh unless
it logs the query rather than the rows.

### 2. Pieces on approval do not move stock

`action_sold` and `action_return` only write `state`. A memo is pieces
physically out with a client, but inventory still counts them on hand, and
"sold" does not create a sale, an invoice or a stock move. The owner's stock
value and the daily gram reconciliation therefore both count metal that is
sitting in a client's house.

This is consistent with the roadmap — sale and invoice wiring is Slice 1 — but
it is worth stating plainly, because the Command Centre shows stock value
today and that figure is currently optimistic by whatever is out on approval.

### 3. Owner cards are not company-scoped

`jewellery.owner.card` has no `company_id`. `_desired()` filters the records
it reads by `env.company`, but the cards it creates carry no company, and
`refresh()` searches all cards with `sudo()`. In a multi-company database the
cards generated for one company are visible from another, subject only to the
restricted-client rule.

For a product aimed at chains of 3 to 20 stores this will matter as soon as a
second company exists. One field and one rule would close it.

### 4. Dead expression in the offer generator

`offer.py` line 40: `partner = partner.sudo() if False else partner`. The
condition is constant, so the line is a no-op; it looks like an abandoned
decision about whether to read the partner as superuser. flake8 does not flag
it. Harmless today, but it hides the intent from the next reader.

## Not found, and worth saying

Nothing in the three addons touches sale orders, invoices, payments, POS,
multi-store transfers, Arabic, or any outbound channel. The product today is
the rate, the engine, the pieces, old gold, the client book and the owner's
cards — which matches what the status table on the landing page says.

## Suggested order, if these are to be fixed

1. Finding 3 (company scoping) — smallest change, and it is a data-leak shape.
2. Finding 2 — falls out of Slice 1 anyway; until then, consider showing the
   on-approval value separately on the Command Centre so the stock figure is
   not read as free and clear.
3. Finding 1 — needs a decision on cost versus completeness before any code.
4. Finding 4 — delete the line next time that file is touched.
