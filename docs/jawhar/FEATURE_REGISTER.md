# Jawhar — Verified Product Capability Register

Statuses: **VERIFIED WORKING** (tests pass on a fresh database and/or a headless walk), **PARTIALLY WORKING**, **PROTOTYPE** (screens or copy without a backend), **PLANNED**, **BROKEN**, **NOT VERIFIED**. "Tests" counts the automated tests that cover the row. Priority: P1 now, P2 next phases, P3 later.

| Feature / module | Status | Completeness | Dependencies | Security gaps | UX problems | Tests | Required fixes | Enhancements | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gold rate, maker-checker (`mumtaz_jewellery`) | VERIFIED WORKING | Full | `stock`, `sale_management` | none known | none | 7 files | — | rate history chart on Rates | P2 |
| Pricing engine (karat, wastage, making, stones, VAT) | VERIFIED WORKING | Full | pure Python | none | — | 19 engine + model tests | — | silver/platinum metals, promotions | P2 |
| Serial pieces, weights, RFID, certificate, cost basis | VERIFIED WORKING | Full | `stock` | none | thumbnails only | yes | — | diamond 4C fields, lot/batch | P2 |
| Stock-book import (CSV/XLSX) | VERIFIED WORKING | Full | openpyxl | manager only | — | 5 + 2 | — | partners/customers import | P2 |
| Old-gold exchange with threshold approval | VERIFIED WORKING | Full | | none | — | yes | — | buyback receipts | P3 |
| VIP tiers, restricted records, access log | VERIFIED WORKING | Full | `mail` | none | — | yes (incl. list/export log) | — | field-level masking of phone for staff | P2 |
| Occasions, memos (stock-moving), ranking | VERIFIED WORKING | Full | | none | — | yes | — | family links (authorised) | P3 |
| Owner decision cards | VERIFIED WORKING | Full, per company | | none | plain list | 2 | — | command centre with lineage (Phase 3) | P1 |
| Sales: frozen rate on line, quote→order→invoice, discount limit | VERIFIED WORKING | Full | `sale`, `account` | none | — | 5 files | — | returns/credit note flow on screen | P2 |
| Counter (online-only, one-transaction commit, old gold, AML gate) | VERIFIED WORKING | Full | | none | receipt styling | yes | site says "offline-capable" (remove) | card terminal integration (decision) | P1 (copy) |
| Pipeline, private tray, client link, viewing, reservation | VERIFIED WORKING | Full | `crm` | token digest, expiry | — | yes | site says "in development" | — | P1 (copy) |
| Outreach drafts, consent, human send | VERIFIED WORKING | Full | | server never sends | — | 14 | site says "in development" | WhatsApp Business API when account exists | P1 (copy) |
| AML/KYC fields, screening, cash-window gate | VERIFIED WORKING | Full; values empty by design | finance manager | none | — | 11 | — | risk scoring (decision) | P2 |
| Stores, transfers, fine-gram reconciliation | VERIFIED WORKING | Full | warehouses | per-store rules | — | 9 | site says "planned" | barcode count | P1 (copy) |
| Channels: rate feed (draft only), web shelf publish | VERIFIED WORKING | Full | HTTPS feed | logged | — | 5 | — | website_sale storefront | P2 |
| Client app (one-time code, owned pieces, trays, consent) | VERIFIED WORKING | Full | | token header, 3 codes/hour | phone only | 8 | site says "planned" | wishlist, rate alerts | P2 |
| Kiosk + Noor + try-on with fit | VERIFIED WORKING (fake camera) / NOT VERIFIED (device, live voice) | Full | ElevenLabs agent config | public, capped | — | 7 + 1 + 12 | register two client tools in ElevenLabs; device test | — | P1 |
| Zayan, Layla agents (levels A–E, drafts, audit) | VERIFIED WORKING | Full | Anthropic key optional | restricted data excluded | — | 18 + 4 | — | evaluation corpus | P2 |
| Rayan, Amara agents | PROTOTYPE (portraits and copy) | 0% | | | catalogue reads as products | 0 | label clearly on the site | specify or drop | P2 |
| Jawhar React app, EN/AR, 26 pages | VERIFIED WORKING | Full for built slices | Vite | session cookie | palette, density | tsc + vitest + walks | — | design system v2 | P1 |
| Public website (7 pages) | PARTIALLY WORKING | Pages render | static | — | stale labels, no forms, text hero | render check | W1–W3 in `PRODUCT_AUDIT.md` | full redesign (Phase 2) | P1 |
| Lead capture / demo request | PROTOTYPE (`mailto:`) | 0% | CRM | consent missing | — | 0 | functional endpoint + form | | P1 |
| Pricing page | PROTOTYPE | placeholder figures | control plane plans | — | reads as prices | 0 | keep banner until approved; drive from plans later | | P2 |
| Setup wizard | PROTOTYPE | creates nothing | provisioner | — | — | 0 | replace with onboarding (Phase 4) | | P2 |
| Tenant provisioning (`mumtaz_tenant_manager`) | NOT VERIFIED (real), VERIFIED (dry run installs) | Partial | Postgres admin | admin credentials handling | — | install only | prove on a disposable host; Jawhar bundle | | P2 |
| Branding (`mumtaz_brand`) | PARTIALLY WORKING | logo, two colours, email, report header | | — | not reaching the React shell | install only | token mapping to the app | typography, favicon, domain | P2 |
| Control plane: plans, features, subscriptions, Stripe | NOT VERIFIED beyond install | Partial | Stripe | webhook idempotency to test | — | install only | tests | metering | P2 |
| Custom domains and SSL automation | PLANNED | 0% | nginx, certbot | | | 0 | | | P3 |
| Procurement, consignment, repairs, workshop | PLANNED (standard `purchase`, `repair`, `mrp`) | 0% | | | | 0 | configure when a tenant needs it | | P3 |
| E-commerce storefront | PLANNED (`website_sale`) | shelf publication exists | | | | 0 | | | P3 |
| Automation engine (events, alerts) | PARTIALLY WORKING (crons, cards) | | `base_automation` | | | | event bus (Phase 6) | | P2 |
| Executive command centre | PARTIALLY WORKING (Today, cards, stores) | | | | lineage not shown | | Phase 3 | | P1 |
| Staging deployment | PARTIALLY WORKING (lags `main` by 8 slices) | | VPS | shared host | | verify_site | promote `main` | separate host | P1 |
