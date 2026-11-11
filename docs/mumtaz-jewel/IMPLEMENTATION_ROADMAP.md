# Mumtaz Jewel: Implementation Roadmap (revision 3)

Date: 2026-11-10. Replaces revision 2. Revision 3 reconciles the v2 Refined Blueprint: see `BLUEPRINT_V2_RECONCILIATION.md` (adds Slice 2B Private Tray; Slice 5 starts read/draft; Slice 6 builds on the tray; Slice 1 adds quote validity and cost basis). Baseline: `docs/MUMTAZ_JEWEL_MASTER_BLUEPRINT.md` (18-section edition). Nothing past Slice 0 starts until you approve this plan.

## 1. Product decisions taken (from you, 10 Nov 2026)

| Decision | Choice | Consequence |
| --- | --- | --- |
| First customer segment | Chains of 3 to 20 stores | Multi-store is core, not later: stock transfers, store-level limits, consolidated owner view, per-store plan pricing |
| Offline POS in the demo | Yes | An offline spike comes first; offline sales sync safely with conflict handling |
| Languages | Arabic and English together | Every screen, receipt, tag, message, voice and AI answer works in both, with right-to-left layout |
| AI | Speaking agents in Arabic and English | Voice stack for owner, staff and clients |
| Customer channel | Conversational app for customers | Client-facing chat and voice app, plus WhatsApp |

Assumptions I am making until you correct them: the app is a white-label progressive web app per jeweller; WhatsApp comes through the Meta Cloud API; Gulf Arabic is the target dialect with Modern Standard Arabic as fallback; demo data is clearly labelled.

## 2. Stance: sell a wedge, not an ERP

The blueprint's pilot slice is product master, piece inventory, pricing, POS and reconciliation. I keep that, but order it by what a chain owner pays for: **rate to price to sale to old gold to daily gold reconciliation across stores, with the owner informed by phone**. Manufacturing, e-commerce sync and a message broker are deferred.

## 3. Mapping to the blueprint phases

| Blueprint phase | This plan | Change |
| --- | --- | --- |
| 0 Discovery | Slice 0 | Mostly done; closes with decisions and test suite |
| 1 Platform foundation | Slices 0 and 4 | Reuse existing control plane |
| 2 Jewellery core | Slices 1 and 3 | Piece identity built; stones and certificates later |
| 3 Pricing engine | Slice 1 | Engine built; sources, approvals, snapshots added |
| 4 Inventory and retail | Slices 2 and 3 | Offline POS and multi-store pulled forward |
| 5 Old gold | Slice 2 | Pulled into the wedge |
| 6 Workshop | Slice 10 | Later |
| 7 Wholesale and VIP | Slices 8 and 9 | VIP core built; dealers later |
| 8 Finance and compliance | Slice 11 | Config packs; confirmer needed |
| 9 AI | Slices 5, 6, 7 | Split into gateway, customer app, voice |
| 10 SaaS hardening | Slices 4 and 12 | Pilot readiness earlier |

## 4. Architecture position (needs your approval, decision D8)

The blueprint is hybrid (Odoo plus independent services). For a small team I propose **Odoo-native first with clean service boundaries**: the pricing engine is already a pure-Python library, the AI gateway and voice layer are separate modules behind an API, and any of them is extracted into a service only when a trigger is hit (rate-feed volume, a public pricing API for e-commerce, reconciliation latency, or isolation needs). This deviates from the blueprint's default, so it needs your sign-off.

## 5. Global risks

| Risk | Mitigation |
| --- | --- |
| Offline POS is hard (double sales of one piece, rate staleness) | Reduced: `POS_NATIVE_AUDIT.md` shows the offline mechanism is standard in Community, so the risk narrows to the rate snapshot and the double-sold serial. Spike those two; offline price uses a locked rate snapshot with a time limit; conflicts go to a visible queue |
| Studio was assumed available; `web_studio` is Enterprise | The ladder for this project is standard config → views and `base_automation` → custom module. Replan anything filed as "Studio will do it" (`ARCHITECTURE_REVIEW.md`) |
| WhatsApp was assumed to be a module; `whatsapp` is Enterprise | Every WhatsApp feature is custom integration against the Meta Cloud API, with template approval and opt-in. Do not promise a date before an account exists |
| A connected scale at the counter may not be available in Community | `iot_base` ships and `product.template.to_weight` exists, but `pos_iot` is **not** among the Community `pos_*` modules. Weigh something on a real scale before promising it to a jeweller |
| Gulf Arabic voice accuracy on jewellery terms | Test set of real utterances validated by native-speaker jewellers before any client exposure |
| Voice and chat leaking private data | Identity check before account facts; restricted clients capped; every answer's numbers come from the engine |
| Recording and privacy law | Consent notices and retention as configuration; to be confirmed by counsel (UAE and each country) |
| 38 existing addons untested | Smoke-test each reused module before depending on it |
| Blueprint states it is a proposed design, not verified against the source catalogue | Reconcile with your original catalogue and a pilot customer's real data in Slice 0 |
| `main` deploys to the VPS | Branch and pull request only; no deploy without approval |

## 6. Slices

Every slice ends with a written test report of actual results.

### Slice 0: Foundation and decisions

Status 10 Nov 2026: **test suite, CI script and seed module done and run**;
actual results in `SLICE0_TEST_REPORT.md` (73 tests, 0 failures: 19
pure-Python plus 54 Odoo `TransactionCase`). The maker-checker bypasses found
while testing are fixed on both approval models (issue 10 below). Still open in this slice: closing
decisions D1 to D8.

Update 11 Nov 2026: the CI script now runs **on GitHub**, not only on a
developer's machine. `.github/workflows/jewel-odoo-tests.yml` builds an Odoo
19 Community checkout against PostgreSQL 16, installs the addons into a
throwaway database, runs the suite and seeds the demo data, by calling the
same `scripts/jewel_ci.sh`. This closes a real hole rather than adding
decoration: everything in `ci.yml` lints, audits and parses, so no job had
ever installed an addon, and GitHub reported green on a commit in this
repository whose Odoo install was in fact broken. A green tick now means the
addons install and the tests pass.

Deploy note, 11 Nov 2026: publishing the site and *serving* it turned out to
be different things. nginx answers 200 with the landing page for any path it
does not recognise, so `/apps/` and `/pricing/` sat unpublished for days while
six URLs, a bogus one included, all returned a healthy-looking 200. Only a
byte comparison revealed it. `deploy/jewel-staging/verify_site.sh` now
fingerprints that fallback and fails any expected page identical to it;
`deploy.sh` runs it after every publish and exits non-zero rather than
reporting success. Separately, the site was being served with no
`Cache-Control` at all, so a correct deploy still showed the previous page in
a fresh incognito window — caches are allowed to invent a freshness lifetime
of roughly 10% of a document's age when none is given.
`deploy/jewel-staging/nginx-cache-headers.conf` has the policy and the apply
steps; it needs a root `nginx -t` and reload on the VPS.

| Item | Detail |
| --- | --- |
| Features | Close open decisions (blueprint section 16 list, D1 to D8). Commit the three Jewel addons to the branch. `TransactionCase` test suite for everything built. CI script (fresh database, install, run tests). Seed module with DEMO data. Fix wording defects |
| Database | Seed module only |
| Odoo | None new |
| Microservices | None |
| API | None |
| UI | None |
| Security | Second review of groups and record rules; tests as five user types including same-user approval refusal |
| Dependencies | Your approvals |
| Tests | Existing 19 unit tests plus new Odoo tests |
| Acceptance | One command installs, tests and seeds a clean database; report lists real counts |

### Slice 1: Price to sale
| Item | Detail |
| --- | --- |
| Features | Rate source adapter (fake feed first), piece cost and real margin, price carried into quote, order and invoice with rate snapshot, dealer-tier discount never on metal, Arabic and English translation files and right-to-left checks started (**the bilingual invoice is standard: install `l10n_gcc_invoice`, do not build a layout** — see `ARCHITECTURE_REVIEW.md`); quote validity with expiry and rate-lock policy (reprice or renew after expiry); price snapshot incl. rule version and rounding; actual cost basis recorded separately from market-value margin; atomic reservation; payment-timeout reconciliation state |
| Database | `jewellery.rate.source`, `.feed.log`; `stock.lot.cost_value`; sale line link and snapshot |
| Odoo | `sale.order` and invoice report extension, bilingual invoice layout |
| Microservices | None (feed is a scheduled action) |
| API | `/rates/*`, `/pieces/{id}/price`, `/quotes` |
| UI | Rate screen, quote form, price panel |
| Security | Maker-checker on rates; price fields read-only on lines |
| Dependencies | Slice 0; rate provider (blocked, fake first) |
| Tests | 30 generated cases equal the engine to the cent; confirmed orders unchanged by later rate changes |
| Acceptance | A 22K quote and invoice match the engine, show the rate used, in Arabic and English |

### Slice 2: Counter, offline and old gold
| Item | Detail |
| --- | --- |
| Features | **Week-one offline spike** on Odoo 19 POS — narrowed by `POS_NATIVE_AUDIT.md`, which found the offline mechanism (service worker, IndexedDB, connectivity detection, sync) already standard in Community, along with serial-per-line, shift close with cash variance, and manager-only price changes. The spike now asks the three questions that are actually ours: which rate an offline sale prices against and when that snapshot expires; what happens when the same serial sells on two offline terminals; and whether the engine's price pushes onto a POS line and survives a sync. Tag scan, price from locked rate snapshot with expiry, offline sale queue with idempotent sync and a conflict queue, old-gold intake and credit at the counter, split payment and deposit, discount limits by role, shift close, bilingual receipts and tags |
| Database | POS line extension, `jewellery.pos.sync.conflict`, `jewellery.pos.shift.report` |
| Odoo | Install and extend `point_of_sale`; service-worker behaviour verified |
| Microservices | None |
| API | `/pos/scan`, `/pos/sync`, `/exchanges*` |
| UI | POS screen (Arabic and English, right to left), conflict queue, shift report |
| Security | Discount limits by group; cash-variance alerts; offline snapshot signed |
| Dependencies | Slice 1; scanner and receipt printer for the demo |
| Tests | Same piece sold offline in two stores resolves to one sale and one conflict; network drop mid-sale; sync retried without duplicates |
| Acceptance | Demo: cut the network, sell a piece with an old-gold exchange, reconnect, books and stock reconcile |

### Slice 2B: Private Tray and client follow-through (new in revision 3)
| Item | Detail |
| --- | --- |
| Features | Preference/intent records with source, confidence and expiry; consent per channel and purpose; eligibility-then-ranking (starting weights 30/25/20/15/10, normalised when signals are missing, confidence shown); 3-5 piece tray; staff review and reorder; branded expiring revocable tokenised link in Arabic and English; client like/dislike/question/viewing request (not a reservation); stored candidate set, reasons, policy version, stock timestamp |
| Odoo | Extend `mumtaz_jewellery_vip` (`nbo.py` becomes the ranking policy) |
| Security | Restricted tiers cannot appear in trays, search, exports or tray links of unauthorised users; tokens stored as digests; no internal IDs in URLs |
| Dependencies | Slice 1 (price and availability); no outbound messaging yet (copy link only). **Most of the tray is standard `crm`: lead, stages, activities, with the reservation a draft `sale.order`. Build only the tokenised link and the ranking** |
| Tests | Expired and revoked links fail; tray never lists sold or reserved-elsewhere pieces; restricted-tier leak tests |
| Acceptance | Associate records budget and preference, shares a tray, client requests a viewing, staff reserve the piece |

### Slice 3: Chain operations and owner view
| Item | Detail |
| --- | --- |
| Features | Stores and vaults, two-sided inter-store transfers, store-level limits and permissions, stock count by barcode (RFID later), daily gold reconciliation in grams per store, consolidated command centre, owner daily summary by WhatsApp (adapter first) in Arabic and English |
| Database | Store, transfer and count tables; reconciliation run table |
| Odoo | Standard multi-warehouse extended |
| Microservices | None |
| API | `/stores/*`, `/transfers/*`, `/counts/*`, `/owner/*` |
| UI | Store switcher, transfer screens, count screen, owner dashboard |
| Security | Staff see only their store; owner sees all |
| Dependencies | Slice 2 |
| Tests | Transfer lost in transit appears in exceptions; count variance in grams; store isolation |
| Acceptance | A three-store demo shows one reconciliation with a seeded variance caught |

### Slice 4: Pilot readiness (SaaS basics)
| Item | Detail |
| --- | --- |
| Features | Stock import from Excel, Jewel plan and module bundle in the control plane (per-store pricing), template-based provisioning, demo mode with one-command reset, backup and restore drill, tenant-isolation tests |
| Database | Plan and bundle rows; import log |
| Odoo | Provisioning template |
| Microservices | None |
| API | Existing control-plane interfaces (read first) |
| UI | Import wizard, tenant status |
| Security | Tenant isolation tests across database, files and jobs. Changing isolation or authentication needs your approval |
| Dependencies | Slices 1 to 3; D5 staging host |
| Tests | New tenant provisions repeatably; restore drill passes |
| Acceptance | A new jeweller workspace is live with imported stock in under a day on staging |

### Slice 5: Conversational platform (shared AI and voice layer)
| Item | Detail |
| --- | --- |
| Features | Tool gateway on `mumtaz_ai`, blueprint autonomy levels A to E, audit log, metering, budget caps, kill switch, injection defence, replayable evaluations, Arabic and English prompt sets, voice stack: speech to text, text to speech, turn handling, with the existing `mumtaz_voice` endpoints as the base |
| Database | `jewel.ai.tool`, `.run`, `.run.step`, `.usage`, voice session extensions |
| Odoo | Extend `mumtaz_ai` and `mumtaz_voice` |
| Microservices | In Odoo first; real-time voice may use a hosted voice-agent provider |
| API | `/ai/tools/*`, `/ai/runs/*`, `/voice/*` |
| UI | Chat panel, run history, approvals queue |
| Security | Start at levels A-C (read, recommend, draft); five agents: Zayan, Amara, Noor, Rayan, Layla (decision D1 — see AI_AGENT_DECISIONS.md); restricted data never enters a model request; runs as the invoking user; money, price and AML tools never above level D with named approval; restricted clients capped at level C; the spoken or written number always comes from the engine |
| Dependencies | Slices 1 to 3; model and voice provider keys via environment |
| Tests | Injection suite; leakage tests; cap enforcement; Gulf-Arabic jewellery utterance set validated by native speakers |
| Acceptance | Same question in Arabic and English returns the same figures, and every call is in the audit log |

### Slice 6: Customer conversational app
| Item | Detail |
| --- | --- |
| Features | Built on the Slice 2B tray page. White-label progressive web app plus WhatsApp: chat and voice in Arabic and English. Browse catalogue, live gold rate, price a piece, indicative old-gold estimate, book an appointment, wishlist and rate alerts, order and repair status, loyalty balance, hand-off to a person. Sign-in by one-time code. No payments by the agent |
| Database | Client session, consent, wishlist, appointment tables |
| Odoo | Public API endpoints behind the gateway |
| Microservices | Next.js front end (per blueprint); gateway in Odoo first |
| API | `/client/*` (auth by one-time code), `/webhooks/whatsapp` |
| UI | Chat, voice, catalogue, appointments, status, alerts |
| Security | Client sees only own data; restricted tiers never receive automated outbound messages or calls; consent captured; rate limits |
| Dependencies | Slice 5; WhatsApp account (blocked) |
| Tests | Client A cannot read client B; injection through client messages; estimates labelled indicative |
| Acceptance | A client asks in Arabic by voice for today's price of a piece and books a viewing; a staff member sees the booking |

### Slice 7: Owner and staff voice assistant
| Item | Detail |
| --- | --- |
| Features | Owner asks by voice in Arabic or English: sales, gold exposure per store, exceptions; staff ask stock and price lookups hands-free; morning voice brief |
| Database | Reuse Slice 5 tables |
| Odoo | Extend the existing CFO voice service |
| Microservices | None |
| API | `/voice/*` |
| UI | Mobile voice screen |
| Security | Voice identity check before figures; owner-only scopes |
| Dependencies | Slice 5 |
| Tests | Same utterance set; wrong-user refusal |
| Acceptance | Owner hears accurate per-store figures that match the dashboard |

### Slices 8 to 12 (shorter; full spec written when reached)

| Slice | Scope | Blockers |
| --- | --- | --- |
| 8 Clients and VIP completion | Wishlist alerts, campaigns, discreet-billing effects, gifting plans | WhatsApp |
| 9 B2B | Dealer tiers, consignment, metal accounts, credit limits, portal | None |
| 10 Workshop | Custom orders, repairs, metal issue and return, job cards | None |
| 11 Compliance and finance | VAT wiring, AML parameters, tax-free scheme, e-invoicing link, metal journals. **`l10n_ae`, `l10n_gcc_invoice` and ZATCA (`l10n_sa_edi`) all ship in Community — this is configuration, not a build** | Named compliance confirmer |
| 12 SaaS hardening | Billing, white-label packaging, disaster-recovery drill, load and security tests | Hosting decision |

Deferred: manufacturing bills of materials, e-commerce synchronisation, message broker, RFID readers (hardware choice), outbound phone-call voice agents.

## 7. Voice agent specification

| Topic | Decision |
| --- | --- |
| Surfaces | In-app voice, owner and staff mobile voice, WhatsApp voice notes. Telephone calls later |
| Languages | Gulf Arabic with Modern Standard Arabic fallback, English; language detected per turn |
| Jewellery vocabulary | Tola, karat, making charge, scrap or old gold, with Arabic equivalents validated by native-speaker jewellers before launch |
| Numbers | Spoken from the pricing engine only, and read back for confirmation before any commitment |
| Identity | One-time code or logged-in session before account data is spoken |
| Autonomy | Read and recommend by default; draft or execute only with named approval; no payments |
| Restricted clients | No automated outbound contact |
| Handover | Always one command away to a person |
| Recording | Consent notice and retention as configuration; legal text confirmed by counsel |
| Quality gate | Utterance test set with accuracy target agreed in Slice 5, run on every prompt or model change |

## 8. Actions that always wait for your approval

Deleting functionality, destructive migrations, replacing the pricing engine, changing production infrastructure, changing authentication or tenant isolation, deploying to production, irreversible financial or business data operations, and deviating from the blueprint's hybrid architecture (D8).

## 9. Unresolved issues

1. ~~Same-user approval block untested (Slice 0).~~ **Closed 10 Nov 2026.**
   Verified on Odoo 19 as five user types; see `SLICE0_TEST_REPORT.md`.
2. Sale, invoice and POS not connected to piece price (Slices 1 and 2).
3. No piece cost, so margin is a proxy (Slice 1).
4. Four ZAKI copies undecided.
5. Offline POS feasibility unproven until the spike.
6. No Arabic translations written.
7. Compliance values awaiting a named confirmer.
8. Blueprint not reconciled against your original source catalogue.
9. Rate provider, WhatsApp account, staging host and voice provider not chosen.
10. ~~`jewellery.gold.rate.state` can be set to `approved` straight through
    the ORM, bypassing maker-checker.~~ **Closed 10 Nov 2026**, on the owner's
    instruction, with a `state` guard: `create` refuses any state but `draft`
    and refuses preset approval fields; `write` refuses `state`,
    `approved_by_id` and `approved_at` unless the write comes from
    `action_approve` or `action_reject`, which run the maker-checker checks
    first. The guard holds for `sudo` too, so a future rate feed enters a
    draft and a person decides on it. Covered by `TestRateStateGuard`.
    The same guard was then applied to `jewellery.old.gold`, where the
    second-person rule above the approval threshold was advisory in the same
    way and an intake could also skip valuation entirely by going straight to
    `confirmed`, leaving it confirmed but never valued. The old-gold guard
    also covers the valuation fields (`rate_id`, `applied_rate_per_g`,
    `value`), so the payout is only ever written by `_price_now` from the
    approved rate. Covered by `TestOldGoldStateGuard`. See
    `SLICE0_TEST_REPORT.md`.
