# Jawhar: feature gap analysis

The register `docs/mumtaz-jewel/CLAUDE.md` requires every change to update.
One row per capability: what it is, whether standard Odoo covers it, what
state it is in, and who has to decide what next.

Sources, all in this folder: `POS_NATIVE_AUDIT.md` (what `point_of_sale`
already does), `FUNCTIONAL_REVIEW.md` (what the three addons do and where
they fall short), `ARCHITECTURE_REVIEW.md` (standard-first options and the
Community module availability). Module availability was read from the Odoo
19.0 Community source, not recalled.

**Status key** — `Built` verified by tests · `Partial` works with a named
limitation · `Standard` ships with Odoo, install and configure · `Planned`
not started · `Gap` needed and nothing covers it · `Decision` waiting on the
owner.

## Interface and API (the product door — `JAWHAR_INTERFACE.md`)

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| JSON API running as the signed-in user, audited | No | **Built** | `mumtaz_jewellery_api`, 11 HttpCase tests |
| Standalone interface, English + Arabic (RTL) | No | **Built** | `apps/jawhar-web`; 18 screens walked on live data |
| Today / owner summary, decision cards | No | **Built** | Partial roles get partial figures, not errors |
| Pieces with the engine's breakdown and dealer discount | No | **Built** | Reprices server-side |
| Clients, Client 360, restricted tiers | No | **Built** | Unreadable client is a 404, not a 403 |
| Quotes, orders, invoices with frozen snapshots | No | **Built** | Read-only in phase 0 |
| Writes from the interface (quote → confirm → invoice → payment) | Partly (`sale`, `account`) | **Built** | Slice 1, level D; 5 API tests + walk |
| Quote validity and rate lock, renewal at today's rate | Partly (`sale.validity_date`) | **Built** | Company days (demo 7); expired quote refuses to confirm |
| Unique piece: sold once, on shelf, not on approval | No | **Built** | Row lock + 4 tests; stock leaves on delivery (counter slice) |
| Cost basis and margin (managers only) | No | **Built** | Recorded, never derived from the engine |
| Self-approval escape hatch | — | **Removed** | Plan W02; a deputy is the second approver |
| Counter from the interface: lookup, readiness, one-call commit, receipt | Partly (`sale`, `stock`, `account`) | **Built** | Slice 3; delivers the ordered serial; 8 + 5 tests + walk |
| Old gold at the till, credited once from a confirmed intake | No | **Built** | Second approval above the owner's threshold |
| Staff discount ceiling (owner-set) | No | **Built** | `mumtaz_jewellery.staff_discount_limit_pct` |
| Offline counter | Partly (`point_of_sale`) | **Decision** | Online-only commitment per plan §11; revisit with a tested allocation model |
| AML cash threshold at payment | No | **Built** | The gate runs at the counter once the named finance manager confirms the amount and the window on the Compliance screen; empty until then, no default (plan §17) |
| Pipeline with jewellery stages, odds from Odoo's scoring | Standard (`crm`) | **Built** | Slice 2; configured, not written |
| Private Tray: eligible stock, ranked with reasons, by hand for restricted tiers | No | **Built** | 11 CRM tests + 2 API tests + walk |
| Client tray link: expiring, revocable, no client data, like/ask/viewing | No | **Built** | A request is not a reservation |
| Outreach: consent on the client (given/withdrawn, how, by whom), occasion drafts one per client per year (level C), a person sends from her own phone (level D, logged); the server never sends | No | **Built** | 14 tests + walk; no consent, no message |
| Agents through the API door: Zayan brief/command bar, Layla tray + follow-up drafts, approvals inbox, audit, pause | No | **Built** | 18 + 4 tests + walk; restricted clients never reach a model; numbers read, never produced |
| Voice and text conversation with Zayan and Layla (ElevenLabs agents, client tools run as the signed-in user), EN/AR, portraits, on every screen | No | **Built** | Model-safe tool results; falls back to server chat |
| Clients and Pieces lists: search, filters, sort, paging, new-client form; demo data at shop scale | Partly | **Built** | 38 clients / 60 pieces in the demo |
| Virtual Sales Officer: public conversational kiosk (Noor, EN/AR), shelf at the approved rate, viewing and next-day delivery requests a person confirms | No | **Built** | 7 + 1 tests + walk; a request is not a reservation |
| Virtual try-on on the kiosk: the camera shows the piece on the client, tracking on the device, nothing recorded | No | **Built** | 5 placement tests + fake-camera walk |

## Pricing and the rate

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Gold rate, two-person approval | No | **Built** | Guarded in `create`/`write`, sudo included |
| Pricing engine (karat, wastage, making, stones, VAT) | No | **Built** | Pure library, 19 unit tests |
| Price per gram / tola / ounce | No | **Built** | |
| Dealer discount on making only | No | **Built** | |
| No price without an approved rate | No | **Built** | |
| Price carried into quote, order, invoice | Partly (`sale`) | **Built** | Slices 1 (sale) and 1b (invoice snapshot) |
| Rate feed adapter | No | **Planned** | Slice 1, provider not chosen |
| Piece cost basis, real margin | Partly (`stock`) | **Planned** | Slice 1 |

## Pieces and inventory

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Serial-tracked pieces, weights, karat | `stock` extended | **Built** | |
| RFID tag, certificate reference | No | **Built** | Tag uniqueness enforced per company |
| Live price on a piece | No | **Built** | |
| Multi-warehouse / per-store stock | **`stock`** | **Standard** | Configure, do not build |
| Inter-store transfers | **`stock`** | **Standard** | Two-sided receipt is configuration |
| Stock count by barcode | **`stock`**, `barcodes` | **Standard** | |
| Daily reconciliation in fine grams | No | **Gap** | Slice 3. Odoo reconciles value and quantity, not grams |

## Counter

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Offline operation | **`point_of_sale`** | **Standard** | Service worker, IndexedDB, sync. Not a build |
| Serial number per sold line | **`point_of_sale`** | **Standard** | `pos.pack.operation.lot` |
| Shift close with cash variance | **`point_of_sale`** | **Standard** | |
| Price changes restricted to managers | **`point_of_sale`** | **Standard** | `restrict_price_control` |
| Barcode / tag scan | **`barcodes`** | **Standard** | |
| Who served | **`pos_hr`** | **Standard** | |
| Price a POS line from the approved rate | No | **Gap** | Slice 2. Must be server-side, not a manual price |
| Rate snapshot and expiry in an offline session | No | **Gap** | Slice 2. The real offline risk |
| Same serial sold on two offline tills | No | **Gap** | Slice 2 |
| Old gold at the till | No | **Gap** | Slice 2 |
| Weight and making breakdown on the receipt | No | **Gap** | Slice 2 |
| Connected scale | **Enterprise** | **Decision** | `iot`/`pos_iot` are not in Community. Weigh on real hardware before promising it |

## Clients

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Tiers, relationship manager, deputy | `res.partner` extended | **Built** | |
| Private / Royal record restriction | `ir.rule` | **Built** | |
| Access log on a restricted client | No | **Partial** | **Only `web_read` logs.** A list view, `search_read`, an export or a report writes nothing. See finding 1 |
| Preferences, usual spend, taste notes | `res.partner` extended | **Built** | |
| Occasion calendar with prepared drafts | No | **Built** | |
| Pieces on approval, reminders | No | **Built** | |
| Pieces on approval move stock | `stock` | **Gap** | State only today, so stock value counts metal that is with a client. See finding 2 |
| Explainable next-piece ranking | No | **Built** | Deterministic, reasons stored |
| Tray: share, viewing request, reserve | **`crm` + `sale`** | **Planned** | Slice 2B. **Mostly standard** — build the token link and the ranking only |
| Loyalty, wishlist, campaigns | **`loyalty`** | **Standard** | Slice 8 |
| Touchpoints across channels | `mail`, `sms` | **Partial** | Email and SMS standard; WhatsApp is not |

## Owner and operations

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Decision cards | No | **Built** | |
| Cards scoped per company | No | **Gap** | No `company_id`; cards cross companies. See finding 3 |
| Consolidated multi-store view | Partly | **Planned** | Slice 3 |
| Owner summary by WhatsApp | **Enterprise** | **Decision** | `whatsapp` is not in Community — Meta Cloud API integration, custom |

## Finance and compliance

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| VAT | **`l10n_ae`** | **Standard** | Install early; painful to retrofit |
| Arabic on invoices and credit notes | **`l10n_gcc_invoice`** | **Standard** | **Do not build a bilingual layout** |
| ZATCA e-invoicing (Saudi) | **`l10n_sa_edi`** | **Standard** | UBL 2.1, certificates, clearance — in Community |
| Old-gold exchange with threshold approval | No | **Built** | Guard covers state, approver and valuation |
| AML / KYC status, screening, risk band | No | **Built** | Identity (type, last 4, expiry), screening and risk band on the client; events log; 11 tests + walk |
| Cash threshold per client per year | No | **Gap** | Shown in the prototype at the till |
| Metal journals | Partly (`account`) | **Planned** | Slice 11 |

## AI and channels

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Agent gateway, autonomy levels, audit | No | **Planned** | Slice 5 |
| Voice (speech in, speech out) | No | **Planned** | Slice 5/7. A demo clip exists; no live stack |
| WhatsApp | **Enterprise** | **Decision** | Custom against Meta Cloud API |
| Client app | No | **Planned** | Slice 6 |

## Platform

| Capability | Standard? | Status | Note |
| --- | --- | --- | --- |
| Odoo 19 Community only | — | **Built** | No Enterprise dependency anywhere |
| Studio | **Enterprise** | **Decision** | `web_studio` is not in Community. The ladder is config → views and `base_automation` → custom |
| Front end | — | **Decision** | OWL inside Odoo keeps the record rules; a separate app re-proves them on an API. See `ARCHITECTURE_REVIEW.md` |
| Repairs | **`repair`** | **Standard** | Slice 10 |
| Workshop / custom orders | **`mrp`** | **Standard** | Slice 10 |
| Multi-company | `base` | **Partial** | New models must carry `company_id` from the start |

## Open findings, by the order I would fix them

| # | Finding | Severity | Why this order |
| --- | --- | --- | --- |
| 3 | Owner cards have no `company_id` | Medium | Smallest change, and it is a leak shape. Do before a second company exists |
| 2 | Pieces on approval do not move stock | Medium | Falls out of Slice 1; until then show the on-approval value separately so stock is not read as free and clear |
| 1 | Access log covers `web_read` only | Medium | Needs a decision on cost: logging every row of a 200-client list is not free |
| 4 | Dead `if False` in `offer.py` | Trivial | **Closed** |

## Waiting on the owner

1. Fix finding 3 now, or wait for a multi-company need?
2. Widen the access log, and if so, log rows or log queries?
3. Front end: OWL inside Odoo, or a separate app?
4. Does `deploy.sh --install` set the Odoo admin password? It is the default on a fresh database today.
5. Should the landing page move to the new indigo, or stay on Mumtaz brand gold?
6. Who weighs something on a real scale before a connected scale is promised?
