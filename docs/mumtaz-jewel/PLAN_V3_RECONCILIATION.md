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
