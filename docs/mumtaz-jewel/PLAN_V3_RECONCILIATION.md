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

## Slice 2 (Sales Hub) — built 11 Nov 2026, plan §7 module 2/3, wireframes 24–26

| Plan element | Delivered |
| --- | --- |
| Pipeline (§7 module 3) | Standard `crm.lead` per client moment with jewellery stages Enquiry → Tray shared → Viewing booked → Reserved → Won; odds are Odoo's own scoring, never typed; the Pipeline screen shows stages, weighted forecast and the next action |
| Private Tray (§7 module 2, wireframe 25) | 3–5 pieces from **eligible stock only** (on the shelf, not on another live order, not out on approval), ranked by the deterministic policy that stores its reasons per line (`nbo-1`); staff keep/remove/add by hand; **Private and Royal clients are never scored** — their trays are chosen by hand |
| Client link (wireframe 26) | Tokenised, expiring (owner-set days), revocable; only the digest is stored; the page carries **no client data and no internal ids**; availability re-checked on every open and a piece that went elsewhere is dropped; like / not for me / ask; **a viewing request is not a reservation** — it opens an activity for staff and moves the stage |
| Royal protocol | No link is ever made for a Royal client (test); a restricted client's tray is invisible to everyone the client record is invisible to (record rule + test) |
| Reservation | Staff reserve → a draft quotation priced from the approved rate; the link dies; the sale's confirmation wins the opportunity |
| Client 360 (wireframe 24) | Trays listed on the client; *Prepare a tray* starts one |

Not built, on purpose: outbound messaging (the link is copied and sent by a person — Outreach is the next slice); the client app beyond the tray page (slice 6).

## Slice 4 (AI agents) — built 11 Nov 2026, plan §12–13, wireframes 20 and 29

| Plan element | Delivered |
| --- | --- |
| Roster (§12) | **Zayan** (coordinator, ceiling B) and **Layla** (client & retail, ceiling C) as working agents in `mumtaz_jewellery_ai`; Rayan, Amara and Noor stay specified, not built (plan's own build order) |
| Execution contract (§13) | Every action is a registered tool run **as the signed-in user** (row/field access as on every screen); each run logged with agent, tool, level, user, model-or-local, tokens, outcome; **refusals are logged results, not errors** (a rolled-back refusal would be no record) |
| Numbers are read, never produced | Prices and figures come from the engine; the model only phrases. A model sentence carrying a number the tools did not supply is **discarded** and the local wording used (test) |
| Restricted clients | A Private or Royal client **never enters a model request** (policy check before any payload; test with a provider that fails the test if called); Layla refuses to rank them and says so |
| Zayan: brief (wireframe 20/28) | Figures with source and time, the decision queue (owner cards + drafts waiting), 3–4 sentences; local wording when no model is configured |
| Zayan: command bar | Intent decided locally first (EN/AR words); the model is asked only to classify, never to act; routes to brief / rate / queue / Layla |
| Layla: tray | Through the same ranking staff use, reasons attached, a draft in the inbox |
| Layla: follow-up | Level C draft for a person to review **and send herself**; a client who asked for no marketing gets a **call note**, never a message; nothing here sends |
| Approvals inbox (wireframe 29) | Team status with ceilings, pending work, the exact text, why-now, sources, owner; **approval binds to the sha256 of the text** — any edit needs review again; return / dismiss; lapse after the owner's days; audit table with refused rows |
| Pause | A jewellery manager pauses the tenant's agents; ordinary screens keep working (test, walk) |
| Provider | Claude Messages API over plain HTTP (the Odoo image is stock `odoo:19`, no SDK); key from the environment only (`JAWHAR_ANTHROPIC_API_KEY`), never stored, never echoed; refusal fallbacks on; **with no key every capability runs on its local path** |

Measured: 18 agent tests + 4 API tests, headless walk (brief, rate, tray by request, follow-up from Client 360, edit → save → approve, Private client refused and audited, pause/resume, Arabic RTL), 0 page errors.

Not built, on purpose: outbound sending (Outreach slice; still a person), voice, Rayan/Amara/Noor, level D anywhere.

## Slice 4b (interactive agents, voice) — built 11 Nov 2026, owner feedback of the same day

| Owner ask | Delivered |
| --- | --- |
| "Agents should be interactive, proper agent photo, a conversational block where we can speak to him, with ElevenLabs capabilities, Arabic and English both" | A conversation drawer on every screen (floating button, portraits of Zayan and Layla). **Voice**: the microphone starts a live ElevenLabs conversational session with the chosen agent; **text** uses the same agent and tools without a microphone; when the voice service is out of reach the drawer falls back to the server's text chat with the same tools. Both agents answer in English or Arabic and switch when the person switches (Arabic language presets with their own first lines). |
| ElevenLabs agents | Two in-app agents, separate from the website guide: *Zayan — Jawhar in-app* (`agent_4201…`, the website Zayan's voice) and *Layla — Jawhar in-app* (`agent_6201…`, a voice designed for her). Eight **client tools** (rate, brief, queue, find client, prepare tray, draft follow-up, search pieces, open screen) that the **browser runs against the Jawhar API as the signed-in user**: the ElevenLabs side holds no key to the shop and no business data of its own. Agent ids are public and configured per tenant (`mumtaz_jewellery.voice_agent_*`). |
| What may leave the building | Tool results are the only business facts the voice model ever sees, and they are the **model-safe** form: the brief and queue exclude Private/Royal cards and drafts (`safe=1`), client search drops restricted clients before answering, trays and follow-ups for them are refused server-side as before. The agent prompts repeat the rules: numbers only from tool results, nothing sent or approved, restricted clients never discussed. |
| "Look and feel too congested, only one client, where is the list, search options, too basic" | Collapsible sidebar; Clients list with search (name/phone/email), tier, **sort** (name, lifetime value, newest), pages of 25, next occasion and phone in the row, and a **New client** form (Private/Royal only for a VIP manager); Pieces list with **category**, sort (serial, price, weight, newest) and paging; demo data at shop scale: 8 designs with categories, 60 pieces, 38 clients across Gulf cities, Arabic-speaking ones marked. A seeded database is **topped up** idempotently (`top_up`), so the staging demo gains the data on upgrade. |

Measured: 29 agent tests (incl. 5 chat tests) + 42 API tests (incl. chat, client create, sort/paging, category); headless walks: drawer opens with portraits and tabs, chat falls back to the server when ElevenLabs is unreachable from the sandbox and still prepares a tray with links, sidebar collapses to 72 px, 38 clients paged and sorted by value, a client created from the form, rings sorted by price. The live voice path is verified on staging after deploy (the sandbox browser has no outbound network).

Next (owner idea, same day): the **Virtual Sales Officer**, a conversational kiosk for clients in store and on the web, with a viewing/hold request and a next-day delivery request that a person confirms.

## Slice 5 (Virtual Sales Officer) — built 11 Nov 2026, owner idea of the same day

| Element | Delivered |
| --- | --- |
| The kiosk | `/app/kiosk`: a public screen for a tablet in the store or the website, no sign-in. **Noor**, an ElevenLabs conversational agent with a designed voice, English and Arabic; tap the portrait to talk, or type. The shelf at the approved rate as cards by category; a piece opens large with the engine's price and the rate it was priced at. |
| What the kiosk may read | Public endpoints under `/jawhar/public/kiosk/*`: the approved rate, the shelf (on-hand, eligible pieces with engine prices, no internal ids, no client data), one piece by serial, the agent id. Five client tools run in the browser against them: rate, search (renders cards), show piece, request viewing, request delivery. |
| What the kiosk may write | **One thing: a request** (`jewellery.kiosk.request`): a viewing / set-aside, or **next-day delivery** (address, morning or afternoon, the date computed). Name and phone only; capped per phone per day; the engine price shown is recorded. The page and the agent both say: *a request is not a reservation; a colleague calls to confirm; nothing is charged here.* |
| What a person does | The request joins the decision queue (Today, the inbox) and the **Client requests** card on the Agents page. **Confirm** matches or creates the client by phone, opens an opportunity, prices a **draft quotation at the approved rate**, and for a delivery schedules the to-do "confirm payment, then dispatch". **Stock does not move** on confirmation; it moves when the order is confirmed and paid, as at the counter (test). **Decline** needs a reason the client is called back with. |
| **Try it on** (owner ask, same day) | On a face- or hand-worn piece the kiosk offers **Try it on**: the tablet camera opens on the screen and the piece is drawn on the client, following her. Tracking runs **on the device** (MediaPipe face and hand landmarks served from the app itself, no cloud call); nothing is recorded, uploaded or stored and the privacy line says so. A design carries a background-free cutout (`jewellery_tryon_image`, public through `/pieces/<serial>/tryon` only for pieces on the shelf); pendants, chains, necklaces and sets hang from the neck, earrings sit on the lobes, rings on the ring finger, bangles and bracelets across the wrist. *Hold this look* freezes the frame; *Set aside for a viewing* goes straight to the request. The demo ships a cutout per design. |
| Rules kept | Online-only commitment: the kiosk never promises availability, never takes payment or card details (the agent refuses them). No client records on the kiosk. Compliance values untouched. |
| The look (owner's concept image, same day) | Portrait teal-and-gold screen: Noor as an illustrated host with a speech bubble that carries her last words, tap-to-talk and a text field, category chips and **photo cards**. Designs carry a photo; the kiosk reads it through a public endpoint for pieces on the shelf, staff see thumbnails on the Pieces list. The demo ships a generated studio photo per design and Noor's avatar, attached on seed and on top-up. |

Measured: 7 kiosk tests (request is not a reservation; validation and the daily cap; confirm creates client, opportunity and a priced draft without moving stock; decline; the queue; the public door carries no ids; the request through the door) + 1 API test; headless walk: kiosk without login, rate and cards, rings filter, piece with the engine rate, viewing request placed with the "nothing reserved" wording, Arabic RTL, the request in the staff inbox, confirmed into a quotation listed under the client's name. Try-on: 5 placement unit tests, headless walk with a fake camera clip (face found, piece drawn on the canvas, hold, Arabic), the public cutout endpoint only for shelf pieces.

## Slice 6 (Outreach) — built 11 Nov 2026

| Plan | Built |
|---|---|
| Consent per client (plan §12, §13) | `marketing_consent` on the client record: not recorded, given, withdrawn; with the date, how it was recorded (in store, phone, signed form, the client wrote) and by whom; a note; written to the chatter. Withdrawn sets the do-not-contact flag; given clears it. Recorded by a person on the client screen or the Odoo form, never by an agent. |
| Occasion-driven drafts (level C) | Each morning Layla drafts the messages for the occasions inside their lead time: **one per occasion per year**, owned by the relationship manager or deputy, channel WhatsApp or email only with recorded consent, otherwise a **call note** that says why. A Private or Royal client's draft takes the local path. On demand from the Outreach screen, the command bar and the chat ("upcoming occasions"). |
| A person sends (level D) | An approved draft is **handed to the named person** as a link that opens the exact approved text in her own WhatsApp or mail client; she presses send there. The server never sends. The hand-over needs the approval to still bind to the text, recorded consent for a message channel, and for a restricted client the relationship manager, deputy or a VIP manager. Who, when, which channel and a note go on the draft, on the client's record and in the audit (`outreach.send`, model "human"). The pause stops preparing, not a person sending what was approved. |
| The screen | **Outreach**: the occasions coming up with consent, the channel a person could use and the draft; approved drafts ready to send; the sent log; the selected draft with its exact text and the hand-over buttons. Consent block on the client record. EN/AR. |

Not built, on purpose: any sending from the server, any message without recorded consent, win-back and upsell campaigns (the ranking exists; a campaign is a later slice).

Measured: 14 outreach tests (consent recorded with who/how/when; withdrawn sets do-not-contact; one draft per occasion per year inside the lead time; no consent → call note; Private client local path and her manager as owner; the paused tenant prepares nothing; command bar and chat route to outreach; hand-over builds the wa.me/mailto link and sends nothing; no consent → no message but a call can be noted; withdrawn blocks approval; only an approved unchanged text; restricted client only by her manager; the pause does not stop a person) incl. 2 through the door; headless walk: 30 occasions with consent tags, prepare, review in the inbox, approve, hand over (the WhatsApp link opens in a new tab), sent log, consent recorded on a client, Arabic RTL, 0 page errors.

## Slice 7 (AML and KYC) — built 11 Nov 2026

| Plan (§17, review R14) | Built |
|---|---|
| Identity on the client | `kyc_status`, document type, **the last four characters only** (a full number is refused), expiry, who verified and when, note; expiry computed; written to the chatter and to the compliance record. Any jewellery user records a document she has seen. |
| Screening and risk | Screening result (not screened / clear / match) and risk band, recorded by a jewellery manager only; a match is a compliance decision and refuses cash at the threshold until a manager clears it. |
| The threshold is configuration | `aml_cash_threshold` and `aml_cash_window_days` are **empty until a jewellery manager with the accounting role confirms them** on the Compliance screen; dated, signed and logged. No default anywhere; a decision card asks finance for the values while they are missing. Nothing here is validated law. |
| The gate at the counter | Readiness carries the payment method and the amount: cash now plus the client's cash in the window (inbound payments on cash journals) against the threshold. At or above it the sale needs a verified, unexpired document and no screening match; else the readiness names why and the commit refuses **in the same transaction, so nothing happened**. A bank or card payment is not cash. A deposit counts only the cash taken now. |
| The record | `jewellery.aml.event`: threshold confirmed, identity verified, screening recorded, cash threshold reached (with the cash now, the cash before, the threshold and the identity snapshot), sale refused. Readable on the Compliance screen and in Odoo; as visible as the client it is about. |
| Agents | Nothing. Identity, screening and AML figures never enter a model request; the agents' client facts do not carry them. |

Measured: 11 AML tests (no threshold until finance confirms and the card asks for it; only a finance manager sets it, dated and signed; identity keeps type, last 4 and expiry only; screening is a manager decision; expiring documents make a card; cash below the threshold passes and the window accumulates; a crossing without identity refuses and nothing happened, the same sale by card goes through; a crossing with identity is allowed and written down; a deposit counts the cash now; an expired document and a screening match refuse, a cleared screening sells; the door: config, identity, readiness and commit) incl. 1 through the door; headless walk: the decision card, the Compliance screen before and after the finance manager confirms a value, the counter refusing cash for a client without identity and saying why, the document recorded on her record (number never stored), the same sale going through, the crossing in the compliance record, Arabic.

## Slice 8 (Stores and transfers) — built 11 Nov 2026

| Plan (roadmap slice 3, review R7/R8) | Built |
|---|---|
| Stores | **A store is a standard warehouse.** Per store: pieces on the shelf, fine grams (net × karat/24), value at the approved rate, an optional fine-gram limit the owner sets, what is on the road in and out, today's count. Staff may be tied to one store (`res.users.jewellery_store_id`); they see their store's transfers and runs, a manager sees all. |
| Transfers | `jewellery.transfer`, **two-sided**: the sending store dispatches (every piece must be on its shelf and on no live order or approval) and the pieces move by standard stock moves to a root internal "Between stores" location: owned and valued, on no shelf, so a count does not expect them. The receiving store receives, and only it. Past the configured days in transit the transfer is overdue; a manager may report it lost, which keeps the metal on the book and raises a card. |
| Reconciliation in fine grams | `jewellery.gold.reconciliation`, one per store per day: a snapshot of the pieces the store should hold with their fine grams; a person scans serials (known ones found, unknown ones listed as extras); the variance is stated in pieces and fine grams with the missing serials named; a manager closes it, with a note when there is a variance. An open variance is a card. |
| Screens | **Stores**: a card per store, transfers with dispatch / receive / report lost, a new transfer by serials, and the day's count per store. Pieces carry their store and the list filters by store. EN/AR. |

Not built, on purpose: barcode counting hardware (serials are typed or scanned into the same box), the owner's WhatsApp summary (no outbound sending anywhere), per-store pricing.

Measured: 9 stores tests (a store is a warehouse with pieces, fine grams and value; dispatch puts pieces in transit and receive lands them, the other store cannot receive for it; only shelf pieces travel and not twice; overdue and lost make cards and lost keeps the metal on the book; staff see their own store only; snapshot, count, variance, close with a note; a piece in transit is not expected on the shelf; store-2 staff cannot see store-1 runs; the door) incl. 1 through the door; headless walk on the demo's two boutiques: the transfer on the road three days, dispatch and receive, the open count with one piece missing, a manager closing with a note, Arabic.

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
