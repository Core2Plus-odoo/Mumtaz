# Jawhar — Product audit (Phase 0)

Date: 21 Nov 2026. Method: the public site rendered page by page at desktop
and phone width with a headless browser; every custom module, test, script,
workflow and deployment file read in the repository; the staging host
checked only through its configuration files, never touched. Each
statement carries one of VERIFIED WORKING, PARTIALLY WORKING, PROTOTYPE,
PLANNED, BROKEN or NOT VERIFIED, as the directive asks. The register itself
is `FEATURE_REGISTER.md`; this document is the narrative.

## 1. What Jawhar is today, verified

- **Engine**: Odoo 19 Community, 13 custom modules under `addons/mumtaz_jewellery*` plus a synthetic demo module. 242 Odoo tests and 19 pure-Python engine tests pass on a fresh database (`scripts/jewel_ci.sh`, run 21 Nov 2026). VERIFIED WORKING.
- **The door**: `mumtaz_jewellery_api`, 64 routes under `/jawhar/v1` that run as the signed-in Odoo user (record rules re-proved by tests: a restricted client is 404, not 403, to staff), plus public routes for the kiosk, client app and tray link that return no internal ids. VERIFIED WORKING.
- **The interface**: `apps/jawhar-web`, React 18 + TypeScript, 26 pages (Today, Cards, Agents, Counter, Clients, Client detail, Pipeline, Tray builder, Public tray, Outreach, Channels, Quotes, Order detail, Invoices, Invoice detail, Memos, Old gold, Pieces, Piece detail, Rates, Stores, Compliance, Documents, Kiosk, Client app, Login). English and Arabic with right-to-left layout and Arabic numerals; every screen walked headlessly with zero page errors. VERIFIED WORKING.
- **Business engine**: gold rate with maker ≠ checker enforced in the model, pricing engine (karat, wastage, making, stones, VAT) as a pure library, approved-rate price frozen on the sale line and invoice, serial pieces with weights/RFID/certificate/cost basis, one live sale per piece (row lock), counter commit in one transaction with old-gold credit and AML gate, memos that move stock, two-sided transfers through a transit location, fine-gram reconciliation per store, stock-book import with preview. VERIFIED WORKING, each with tests.
- **Clienteling**: tiers with restricted Private/Royal records, access log for form, list and export, preferences and occasions, explainable next-piece ranking, private tray with expiring token link, consent and outreach drafts a person sends from her own phone, KYC fields and screening, client app by one-time code. VERIFIED WORKING.
- **AI**: Zayan and Layla as tool-using agents with autonomy levels A–E, drafts with digest-bound approval, audit of every run, restricted data never in a model request, numbers never produced by a model; Noor as the public kiosk agent with client tools, try-on with on-device face/hand/body tracking and fit estimates. VERIFIED WORKING (model calls optional; voice verified only with a fake device, live voice NOT VERIFIED).
- **Staging**: `jewel.mumtaz.digital` serves the static site publicly and the app, Odoo and API behind HTTP basic auth, from an isolated compose project with its own database. Deployed up to the kiosk slice; eight later slices are on `main` but not yet deployed. PARTIALLY WORKING (lag, not defect).

## 2. The public website versus the product

The site has seven pages (home, apps, pricing, setup, intelligence, preview, Sales Hub module). Rendered at 1440 and 390 px: no horizontal scroll, no broken images, no console errors. Findings:

| # | Finding | Severity | Status label |
| --- | --- | --- | --- |
| W1 | **Readiness labels are stale and understate the product.** Home shows Counter, Sales Hub, Outreach and Intelligence as "In development" and Stores, Channels, AML & KYC as "Planned"; the status table says the tray, price-on-invoice, counter, Arabic are "In development" and client app, transfers "Planned". All are built and tested. The footnote claims "73 automated tests"; the figure is 242 + 19. The Sales Hub page repeats the stale labels. | High | BROKEN (as information) |
| W2 | **"Offline-capable" appears on the pricing page** (Counter card) and the preview's counter note says the counter sells offline against a locked rate. The counter is online-only by decision; the apps page already dropped the claim. | High | BROKEN |
| W3 | **No functional lead capture.** Every "Request a demo" is a `mailto:`; zero forms on seven pages; no consent capture; nothing reaches the CRM. | High | PROTOTYPE |
| W4 | **Pricing page shows figures** labelled "placeholder, not an offer" in a banner; the figures still read as prices. Pricing is not approved. | Medium | PROTOTYPE |
| W5 | **Setup wizard creates nothing** (its banner says so). No onboarding backend exists. | Medium | PROTOTYPE |
| W6 | **Intelligence page**: Zayan and Layla are real; Rayan and Amara are portraits and copy only; the page says so in a banner but the catalogue reads as five products. | Medium | PARTIALLY WORKING |
| W7 | **Imagery**: 17 images, all product screenshots or generated portraits; no jewellery, boutique or craft photography; the hero is a text card. | Medium (brand) | — |
| W8 | **Design**: indigo accent (`--gold:#3D56C4` is actually blue), grey paper, single typeface; competent SaaS, not luxury; identical card grids repeated; the token names contradict their values. | Medium (brand) | — |
| W9 | `noindex, nofollow` on every page and `location = /` in nginx; no sitemap, no structured data, English only, no Arabic site. | Medium (growth) | — |
| W10 | Accessibility: 4 ARIA attributes on the home page, 5 empty `alt`s on the preview, burger menu is a CSS checkbox with a label acting as a button; reduced-motion respected (one query). | Low | — |
| W11 | Demo system link goes to `/odoo` behind basic auth with no explanation of how to get credentials. | Low | — |
| W12 | Contradictions with Enterprise: none found; the site says Community throughout. Payment-splitting: none suggested; the preview's AML copy is in line with the counter gate. | — | Clear |

## 3. The application experience

- Strengths: one design language across 26 pages, RTL done properly, tabular numerals, status tags, worklists, every money figure next to its rate; headless walks in both languages.
- Weaknesses: the palette is the same indigo-on-grey as the site; density is high on Today; the kiosk uses a separate teal theme; no empty-state illustrations; no photography beyond piece photos; the shell has no company/store switcher for multi-store users; no dark mode in the app (the site has one).
- Not verified on a device: camera try-on with a real person, live voice sessions, tablet ergonomics at the counter.

## 4. SaaS and white-label: what exists and what does not

- Exists on the **platform** side (`addons/mumtaz_*`, not Jawhar-specific): `mumtaz.tenant` (database name, subdomain, custom domain, state, brand link, admin), module bundles, a dry-run and a real provisioner (create database → install modules → admin user → settings), `mumtaz.brand` (product name, logo, favicon, two colours, email sender, report header/footer, portal welcome), control plane (plans, features, subscriptions, usage, Stripe billing, API keys), subdomain routing with host→database resolution. All without tests until this week's install CI; the real provisioner is NOT VERIFIED against a live host.
- Does not exist: Jawhar as a provisionable bundle, per-tenant branding reaching the Jawhar React shell, custom-domain/SSL automation, trials and plan changes end to end, resource metering, backups per tenant, safe offboarding/export, reseller role separation. PLANNED.

## 5. Security posture (verified this week)

Record rules and negative tests on every Jawhar model; `sudo()` labelled and CI-checked across the repository (265 sites); the three places that served data to any signed-in user closed; company scoping across platform modules; secrets by environment and encrypted at rest; public doors rate-capped. Open: MFA not enforced; staging shares one host with production; restore drill not evidenced; no penetration test.

## 6. What to preserve, refactor, complete, replace, build

| Decision | Items |
| --- | --- |
| **Preserve** | The 13 modules and their tests; the door and its rules; the pricing engine; the React app's structure, i18n and walks; the staging deploy guards. |
| **Refactor** | Design tokens (site and app) into one Vibrant Luxury Enterprise system; the kiosk theme folded into it; the site's page templates. |
| **Complete** | Readiness labels; functional lead capture with consent into the CRM; Jawhar tenant bundle on the provisioner; brand → app shell; device verification of try-on and voice. |
| **Replace** | The static pricing figures with a plan model driven from the control plane once prices are approved; the setup prototype with the onboarding flow (Phase 4). |
| **Build new** | Owner command centre with lineage; procurement, consignment, repairs/workshop on standard Odoo; automation engine on `base_automation` + events; AI orchestration layer generalised from Jawhar's policy; white-label configuration end to end. |

## 7. Risks

Stale claims on the public site (credibility), single-host staging, no MFA, provisioner unverified, image rights for marketing (use generated or owned only), voice/try-on unverified on devices, prices not approved, Enterprise temptation for assets/budgets/quality (stay Community + OCA).
