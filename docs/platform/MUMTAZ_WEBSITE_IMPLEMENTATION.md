# Mumtaz Digital website — implementation status

Scope: the public website `mumtaz.digital`. Read-only evaluation of every
website implementation in this repository, first made at commit `2c2939a` and
re-checked against `ff1c797` (after PR #187) on 21 Nov 2026.

**Nothing has been deployed by this work. The live homepage was not touched.
No server was inspected: this session has no access to it.**

Status tags used on every row:

| Tag | Meaning |
| --- | --- |
| **VERIFIED** | Read in code at the cited path, at `ff1c797` |
| **REPORTED** | Stated in a repository document; not re-checked here |
| **PROPOSED** | Recommendation; not built |
| **UNKNOWN** | Needs evidence from the server |

Related documents (not duplicated here): `docs/mumtaz-website/README.md`
(install guide and test record of the module), `MUMTAZ_DESIGN_SYSTEM.md`
(tokens and brand), `docs/erp/project/DECISION_REGISTER.md` (D-09, D-11,
D-13), `docs/infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md`,
`sites/mumtaz.digital/README.md`.

## 1. Conclusion

1. `addons/mumtaz_website_builder` is the canonical implementation. It is the
   only one built on the native Odoo 19 Website module and editable in the
   Website Builder, it installs without changing anything a visitor sees, and
   it has tests. **VERIFIED**
2. It is not ready to publish. The hero shows a drawn mock with invented
   figures instead of a real product demonstration; since PR #187 the page
   also carries prices and compliance claims that are undecided (D-11) or
   have no supporting code; colours are hardcoded; there is no Arabic or RTL
   work, no SEO metadata, no captcha, and the header, footer and logo are
   stock Odoo. **VERIFIED** (details in §4)
3. Where it should run is not decided. One document now names the `Mumtaz_ERP`
   database in a production command; no decision records that choice, and
   whether the module is installed there is **UNKNOWN** (§5).

## 2. Requirement check

| Requirement (directive) | Result | Evidence | Tag |
| --- | --- | --- | --- |
| Built on the native Odoo 19 Website module and Website Builder | Met | Depends on `website`, `website_crm` (`addons/mumtaz_website_builder/__manifest__.py:9`). Ten `<template>` blocks (`views/snippets/mumtaz_blocks.xml:3,31,43,49,54,67,72,77,89,106`) registered in the builder library under group "Mumtaz Digital" (`views/snippets/mumtaz_snippets.xml:3-38`). Page is a `website.page` inside `website.layout` with a literal `#wrap.oe_structure` (`data/website_page.xml:3-13`) | VERIFIED |
| Homepage headline "Run the business. Not the software." | Met | `views/snippets/mumtaz_blocks.xml:8` | VERIFIED |
| Hero with a **real** product demonstration | **Not met** | The hero visual is CSS-drawn markup labelled "Illustrative data" with "AED 284,000", "38", "92%" (`mumtaz_blocks.xml:18-23`). The module has one raster image, an illustrated ring (`static/src/img/content/jawhar_visual.png`, 666×537). No product screenshot or recording | VERIFIED |
| Three choices: General ERP / Industry Solutions / White-Label ERP | Met | `mumtaz_blocks.xml:36-38` | VERIFIED |
| Key ERP capabilities | Met | Eight tiles: Finance, Sales, CRM, Procurement, Inventory, HR, Operations, ZAKI AI (`mumtaz_blocks.xml:45`) | VERIFIED |
| Industry solutions including Jawhar | Partly | Jawhar "● Available", Pharma and Retail "◌ Planned" (`mumtaz_blocks.xml:51`). "Available" links to `https://jewel.mumtaz.digital/`, which is marked `noindex, nofollow` (`website/jewel/index.html:13`) and is a staging/demo host (REPORTED, `sites/jewel.mumtaz.digital/README.md`) | VERIFIED |
| ZAKI | Partly | Section present and labelled "ILLUSTRATIVE" (`mumtaz_blocks.xml:69`). The FAQ added by #187 states as fact that ZAKI "delivers a 60-second spoken briefing every morning" (`mumtaz_blocks.xml:100`); see `MUMTAZ_AI_ARCHITECTURE.md` for what the ZAKI code does | VERIFIED |
| Demo / partnership call to action | Met | Native `s_website_form` posting to `crm.lead` (`mumtaz_blocks.xml:110-126`), server-side validation and tagging (`controllers/website_form.py:29-63`), partnership link (`mumtaz_blocks.xml:74`) | VERIFIED |
| "Do not overwrite the live Mumtaz homepage without approval" | Met by the code | Install creates one page with `is_published=False` at `/mumtaz-native-preview`, file-level `noupdate="1"` (`data/website_page.xml:2-8`); nothing writes a homepage or a menu. A test asserts this (`tests/test_website_builder.py:20-28`) | VERIFIED |
| Same, on the server | — | Whether the page has been published or set as homepage on any database | UNKNOWN |

## 3. Every website implementation in the repository

| Implementation | What it is | Verdict | Tag |
| --- | --- | --- | --- |
| `addons/mumtaz_website_builder` (19.0.1.0.0) | Ten Website Builder blocks, one unpublished page, four CRM tags, one scoped stylesheet, a form-validation controller, seven `HttpCase` tests | **Keep — canonical** | VERIFIED |
| `addons/mumtaz_website` (19.0.1.0.0) | Four controller-rendered pages at `/mumtaz`, `/mumtaz/features`, `/mumtaz/pricing`, `/mumtaz/contact` (`controllers/main.py:7,11,15,27`). Not builder-editable. Own palette (gold `#f0a500`, blue `#3b82f6`; `static/src/css/website.css:7-14`). Ships unscoped `*{box-sizing}` and `body.website{…}` into the shared frontend bundle (`website.css:24-26`). Hardcoded fallback prices 999 / 2,499 and a 14-day trial (`views/pricing.xml:67,84,126`), otherwise reads `mumtaz.plan` under `sudo()` (`controllers/main.py:20`). Marked superseded in `registry/classification.json:116-120` | **Retire** after cut-over | VERIFIED |
| `addons/mumtaz_api` | Public CORS lead API for the static site: `/api/mumtaz/v1/demo`, `/contact` creating `crm.lead`; origins fixed to `mumtaz.digital` (`controllers/api_v1.py:9-11,82,129`) | **Retire with the static site**, or fold the two routes into the builder module if still needed | VERIFIED |
| `sites/mumtaz.digital/site/` | 14 static pages. Contact form is fake: `handleContactSubmit` only swaps the form for a success message (`contact.html:154,284`). Six pages link to the server's raw IP on port 8069 (`about`, `blog`, `demo`, `docs`, `platform`, `solutions`). Prices AED 99 / 299 and several unverified claims (REPORTED from the evaluation: `pricing.html:109,135,173,196-197,297`). Published by `ops/deployment/deploy-website.sh` to `/var/www/mumtaz.digital` | **Keep as content reference, then retire** | VERIFIED |
| `sites/delivery.mumtaz.digital/landing/` | One page titled "Mumtaz — ERP, delivered by AI"; every call to action goes to `https://delivery.mumtaz.digital` (`sites/delivery.mumtaz.digital/landing/index.html:6,30,31,46`). It markets the delivery console, not Mumtaz. CI only checks the files exist (`.github/workflows/ci.yml:310`) | **Retire from the Mumtaz site** (or move to the delivery console). The CI job must change in the same pull request | VERIFIED |
| `platform/marketing/index.html` | One page; prices $49 / $199 (`:350,353`); "permanently free" e-invoicing (`:7,214,336,454`); form posts to `https://app.mumtaz.digital/api/public/contact` (`:496`), a path with no backend in this repository | **Keep as reference, then retire.** Needed for rollback and the redirect map | VERIFIED |
| Same copy, live status | The live page title matched this copy on 21 Nov 2026 (`REPO_MAP.md:76`) | — | REPORTED |
| `website/jewel/` (Jawhar public site) | Seven static pages (home, apps, modules/sales-hub, intelligence, preview, pricing, signup), `noindex`, real product screenshots, a working form to `/jawhar/public/site/demo-request` (`website/jewel/index.html:413`). Token sheet `website/jewel/site/jawhar.css` | **Keep** as the Jawhar site and as the token source | VERIFIED |
| `addons/mumtaz_jewellery_website` | Demo-request endpoint for the Jawhar site with honeypot, stored consent and a daily cap (`controllers/public_site.py:37-47`); five tests (REPORTED) | **Keep**; reuse its consent handling | VERIFIED |

Four nginx definitions for the apex domain are in git, with two different web
roots: `/var/www/mumtaz.digital` (`ops/deployment/nginx-mumtaz-digital.conf:15`,
`sites/mumtaz.digital/site/nginx.conf:21`, and
`ops/deployment/nginx-mumtaz-platform.conf`) and `/opt/mumtaz/marketing`
(`platform/ops/nginx/mumtaz.digital.conf:9`). **VERIFIED.** Which one is
active is **UNKNOWN**.

## 4. Gaps in the canonical module

### 4.1 Facts about the module at `ff1c797`

| Topic | Finding | Tag |
| --- | --- | --- |
| Blocks | Ten: hero, paths, platform, editions, localisation, ZAKI, partners, pricing, FAQ, contact. Seven at `2c2939a`; PR #187 added localisation, pricing and FAQ | VERIFIED |
| Page | One `website.page`, ten sections in `data/website_page.xml`, no `website_id`, no menu | VERIFIED |
| Snippet options | None. No options XML, no JavaScript, no builder plugin | VERIFIED |
| Tests | Seven `HttpCase` tests (`tests/test_website_builder.py:20,30,46,57,70,96,115`): install footprint; ten sections render for an administrator; literal wrap; registration; stylesheet bundle integrity; tagged lead with consent line; server refusals and other forms unaffected | VERIFIED |
| CI | `scripts/platform_ci.sh` installs every non-jewellery addon in one database and runs each module's tests. Result of the latest run | UNKNOWN |
| Reported result | "7 tests, 0 failed, 0 errors" on a fresh database (`docs/mumtaz-website/README.md:65`) | REPORTED |
| Stylesheet | One CSS file, 80 lines (`static/src/css/mumtaz_builder.css`); no SCSS | VERIFIED |
| Fonts | Loaded from Google Fonts by `@import` (`mumtaz_builder.css:2`). Not self-hosted. Glyph rendering never confirmed (`docs/mumtaz-website/README.md:74`) | VERIFIED / REPORTED |
| Tokens | Seven `--mm-*` variables defined (`mumtaz_builder.css:3`). Used: `--mm-lime` ×7, `--mm-navy` ×2, `--mm-ink` ×1. Never used: `--mm-deep`, `--mm-mint`, `--mm-paper`, `--mm-muted`. 104 distinct six-digit hex literals | VERIFIED |
| RTL / Arabic | No `i18n/` folder, no `[dir=rtl]` rule, no Arabic font, no logical properties, 13 physical left/right declarations, negative letter-spacing on headings (−.04 to −.07em) | VERIFIED |
| Focus / motion | No `:focus` rule. One `prefers-reduced-motion` rule exists | VERIFIED |
| SEO | Only `additional_title` (`data/website_page.xml:12`). No description, Open Graph, structured data or hreflang | VERIFIED |
| Form validation | Applies only when the hidden subject equals a fixed string (`controllers/website_form.py:19,32`) and the solution is one of four fixed values (`:20-25,50`) | VERIFIED |
| Consent record | One line "Privacy consent : Yes" in the lead description. No stored wording, timestamp or cap | VERIFIED |
| Anti-spam | Honeypot and size cap only (`website_form.py:59-63`). Captcha is a manual step (`docs/mumtaz-website/README.md:118,128`) | VERIFIED |
| Side effects on a shared database | The block group shows in every website's editor; the Google Fonts import joins the shared frontend bundle; `tag_ids` becomes settable from any website form on the database (`data/crm_tags.xml:12-15`) | VERIFIED |

### 4.2 Content now on the page that is not backed by a decision or by code

PR #187 carried the previous static site's pricing, FAQ and localisation copy
into the page at the owner's request. `docs/mumtaz-website/README.md:12-15`
records that these are "the owner's published claims, not something verified
here". They must be resolved before publication:

| Statement on the page | Where | Problem | Tag |
| --- | --- | --- | --- |
| Starter $49, Growth $199, add-ons $20 / $25 / $12 / $35 / $15 | `mumtaz_blocks.xml:82` | D-11 is open: three price lists exist ($49/$199; $149/$399/$999; AED 99/299), plus bundle prices in `addons/mumtaz_tenant_manager/data/mumtaz_bundle_data.xml`. No `mumtaz.plan` record is seeded anywhere | VERIFIED |
| Org Starter $8 / SME, Org Business $6 / SME | `mumtaz_blocks.xml:84` | Same | VERIFIED |
| "These modules are permanently free and installed automatically for every tenant" | `mumtaz_blocks.xml:63` | No install profile includes `mumtaz_einvoicing` (`mumtaz_bundle_data.xml`); the module has 0 test files (`registry.yaml`, entry `mumtaz_einvoicing`) | VERIFIED |
| UAE: "FTA auto-submission" | `mumtaz_blocks.xml:59` | `addons/mumtaz_einvoicing/services/uae_vat_service.py` builds a QR code and validates a TRN; it makes no network call | VERIFIED |
| KSA: "ZATCA Phase 2 … cryptographic signing, API clearance"; PK: "direct portal submission" | `mumtaz_blocks.xml:60-61` | Code exists (`services/zatca_service.py`, `services/fbr_service.py`) but is untested; whether it has ever cleared a real invoice | UNKNOWN |
| "Activate it in one click from app.mumtaz.digital"; "Adding a module installs it instantly"; "cancel from app.mumtaz.digital" | `mumtaz_blocks.xml:95,99,101` | The portal's backend source was deleted from the repository (REPORTED, `sites/app.mumtaz.digital/README.md`); see `MUMTAZ_SAAS_CONTROL_PLANE.md` | REPORTED |
| "Your data is … held for 90 days post-cancellation" | `mumtaz_blocks.xml:101` | A retention commitment with no implementing code found and no verified backup (audit finding F-02) | REPORTED |
| "Every business gets its own PostgreSQL database" | `mumtaz_blocks.xml:97` | True of the tenant model (ADR-002); `mumtaz_org_config` implements company-per-organisation in one shared database | REPORTED |
| ZAKI "delivers a 60-second spoken briefing every morning" | `mumtaz_blocks.xml:100` | See `MUMTAZ_AI_ARCHITECTURE.md` | REPORTED |
| "a person from Mumtaz Digital will reply within two working days" | `mumtaz_blocks.xml:126` | A service commitment; who owns it is not recorded | VERIFIED |
| "No setup fee. No contract." | `mumtaz_blocks.xml:85` | Commercial terms; not recorded as decided | VERIFIED |

### 4.3 Gaps against "publishable"

- No real product demonstration (§2). **VERIFIED**
- Undecided prices and unsupported claims are on the page (§4.2). **VERIFIED**
- Tokens are not reusable and not white-label configurable: nothing links the
  colours to Odoo's theme colours or to `mumtaz.brand`. **VERIFIED**
- Fonts come from a third-party host. **VERIFIED**
- No RTL or Arabic work. **VERIFIED**
- Header, footer, logo and favicon are stock Odoo (`docs/mumtaz-website/screenshots/home-desktop.jpg`). **REPORTED**
- One page only. The consent sentence needs a privacy page; none exists. **VERIFIED**
- No SEO metadata; the URL is a preview slug. **VERIFIED**
- "Available" points at a `noindex` staging host. **VERIFIED**
- Focus states are not styled. **VERIFIED**
- Module documents are out of step with the code: the manifest description and
  `addons/mumtaz_website_builder/README.md` say seven blocks and "no custom
  controller"; `docs/mumtaz-website/README.md:51` says six tests, line 65 says
  seven, lines 67, 70 and 94 still say seven sections or blocks. **VERIFIED**

### 4.4 Gaps against "non-technical staff can maintain it"

| Gap | Tag |
| --- | --- |
| No snippet options: colour, layout variant and card count cannot be changed from the side panel | VERIFIED |
| The form stops validating, or refuses every submission, if an editor changes the hidden subject or the option values in the builder (`controllers/website_form.py:19-25,32,50`) | VERIFIED (consequence inferred) |
| Emphasis colour depends on a `<span>` inside headings; retyping a heading can drop it | PROPOSED check on staging (inferred, not run) |
| Chart bars use inline `--h` styles and empty elements are held open with zero-width spaces (`mumtaz_blocks.xml:17,23`); both need the HTML editor | VERIFIED |
| Cards are CSS-grid `div`s, not Bootstrap columns; adding a fourth path or a ninth tile from builder handles is unlikely to work | PROPOSED check on staging (inferred) |
| Page markup and block templates are two hand-kept copies. The "build step" that regenerates one from the other (`docs/mumtaz-website/README.md:50`) is not in the repository. `scripts/mumtaz_site_add_blocks.py` only inserts the three new blocks into an existing page | VERIFIED |
| No Arabic translation file and no editor guide | VERIFIED |

## 5. Where it should run

### 5.1 What the repository says today

- `addons/mumtaz_website_builder/README.md` says "staging database first" and
  names no database. **VERIFIED**
- `docs/mumtaz-website/README.md:35,126` says production was not inspectable
  and the module was not run on any server. **REPORTED**
- `docs/mumtaz-website/README.md:110` (added by #187, section "production")
  gives a command against config `/etc/odoo2.conf`, database `Mumtaz_ERP` and
  checkout `/opt/mumtaz-main`. This implies the page lives, or is meant to
  live, in the ERP database. **VERIFIED** that the document says so.
- Whether `mumtaz_website_builder` is installed in `Mumtaz_ERP`, whether the
  page is published there, and whether the apex domain points at it. **UNKNOWN**

### 5.2 Recommendation (PROPOSED)

A dedicated Odoo 19 Community instance with its own database, used for the
public website and its leads and nothing else.

| Item | Proposal |
| --- | --- |
| Pattern | Copy the Jewel staging setup (`deploy/jewel-staging/`): Docker `odoo:19`, own PostgreSQL, addons mounted read-only, bound to `127.0.0.1`, behind nginx |
| Configuration | `db_name` set, exact `dbfilter`, `list_db = False`, `/web/database/*` denied at the proxy |
| Database name | Must not start with `Mumtaz`: the `odoo` service filters on the prefix `^Mumtaz` (REPORTED, `docs/infrastructure-audit/06_ODOO_INSTANCES_AUDIT.md:10,26`) |
| Addons path | Only the website module(s), not all of `addons/`, so `mumtaz_theme`, `mumtaz_website` and `mumtaz_organization` cannot be installed there by accident |
| Modules | `website`, `website_crm`, `crm`, a captcha module, `mumtaz_website_builder` |

Why not an existing database (all REPORTED, audit document 06, unless marked):

| Database | Reason |
| --- | --- |
| `Mumtaz_ERP` | Holds the tenancy and control-plane modules, with open critical findings (shared sign-on secret, finance exposure). A public site there shares the login surface, the session cookie domain and the upgrade cycle with the ERP. If the page is already installed there (§5.1), moving it is a small step now and a larger one after publication |
| `Mumtaz_C2P` | Production group CRM; server actions on `crm.lead` stored only in the database would fire on website leads; two services are bound to it; its addons come from a feature branch |
| `Mumtaz_IG2` | An external client's ledger |
| `jewel_demo`, `mumtaz_pharma` | Staging |
| Any shared database | The module's side effects (fonts import, block group, form whitelist) reach every website in it (VERIFIED, §4.1) |

### 5.3 Relation to `app.mumtaz.digital` and lead destination

- The control plane stays separate. The website holds no tenant data and
  shares no session with it. **PROPOSED**
- The website links to `app.` for sign-in or trial only once that service is
  verified working (`MUMTAZ_SAAS_CONTROL_PLANE.md`). Until then the only call
  to action is the demo form. **PROPOSED**
- Show no prices until D-11 names one price source. **PROPOSED**
- Leads: either worked in the website database's own CRM, or pushed to
  `Mumtaz_C2P`. Nothing in the repository decides this. **UNKNOWN — owner
  decision**

## 6. Cut-over plan

Nothing below has been done.

### 6.1 Checks on the server first (read-only)

1. `nginx -T` for the apex: which vhost and root are active; checksum of the
   served `index.html` against the three repository copies.
2. Domain registration and certificate state (audit F-10 records a "lapsed" note).
3. Whether `app.mumtaz.digital/api/public/contact` answers — whether the live
   form delivers enquiries today.
4. Per database: state of `website`, `website_crm`, `mumtaz_website`,
   `mumtaz_website_builder`, `mumtaz_theme` in `ir_module_module`; rows of
   `website` (domain, `homepage_url`); whether the preview page is published.
5. Free memory and CPU for one more instance; PostgreSQL version; whether
   `rtlcss` is installed (needed for Arabic).
6. Access-log top URLs of the current site, for the redirect map.
7. Outbound mail for lead notification; captcha keys.
8. A backup target for the new database and its filestore (the audit found no
   filestore backup anywhere).

### 6.2 Steps (each needs a named approval)

1. Decide D-09, D-11, D-13 and the lead destination.
2. Stand up the instance on a staging hostname with basic authentication and
   `noindex`; install the module.
3. In that database: set the website's name and domain, logo, header and
   footer, languages, default sales team and captcha; assign the page's
   website; close the gaps in §4.
4. Run the module tests there, one real form submission, and RTL,
   accessibility and performance checks; the owner signs off on the staging URL.
5. Set the page as homepage **inside the new database only**, where `/` has no
   earlier content, so nothing existing is overwritten.
6. Back up the database; archive the current static root and vhost file.
7. On named approval, switch the apex with one new nginx vhost that proxies to
   the instance. Leave the old static root and vhost file on disk.
8. Add redirects for old URLs; remove `noindex`; submit the sitemap.
9. After a soak period, retire the static copies and `mumtaz_website`, one
   pull request per row of §3.

### 6.3 Rollback

Re-enable the old vhost file and reload nginx. The static root is still on
disk, so the previous site returns unchanged. The new database is left as it
is for inspection; nothing is dropped.

## 7. Decisions for the owner

| ID | Decision | Recommendation |
| --- | --- | --- |
| D-09 | Which marketing site is canonical | `mumtaz_website_builder`; archive the three static copies after cut-over |
| D-11 | One price list, and which claims may be published ("permanently free", "no contract", 90-day retention, two-working-day reply, FTA / ZATCA / FBR wording) | Remove the pricing block and the unsupported sentences from the page until each is decided and evidenced; then one source of prices (`mumtaz.plan`) |
| D-13 | One brand source | See `MUMTAZ_DESIGN_SYSTEM.md` |
| New | Where the website runs | Dedicated instance and database (§5.2) |
| New | Where website leads are worked, and who replies | Owner to name the team and the CRM |
| New | Captcha provider and keys; privacy page text | Turnstile or reCAPTCHA; a privacy page before the form goes live |
| New | Real product demonstration for the hero | A screenshot or short recording of the actual ERP on demo data, replacing the drawn mock |

## 8. Could not determine

- Which copy nginx serves at `mumtaz.digital` today, from which root, and
  whether the domain and certificate are healthy.
- Whether the live contact form delivers anything.
- Which Odoo databases have `website` installed; whether `mumtaz_website`,
  `mumtaz_website_builder` or `mumtaz_theme` is installed anywhere.
- Whether the preview page exists or is published in `Mumtaz_ERP`.
- Whether the latest CI run of the seven tests was green. No test was run for
  this document.
- Editor behaviour in practice: card duplication, heading span survival,
  whether builder background presets override the module's colours.
- Whether `body.website` from `mumtaz_website` matches Odoo 19's body class.
- Whether `rtlcss` is on the server, and how the page looks in Arabic.
- Whether Space Grotesk and Inter actually render.
- Which price list is correct, and whether the compliance, retention and
  response-time statements are true.
- The "Website Implementation Directive of 21 Nov 2026" that
  `docs/mumtaz-website/README.md:4` cites is not in the repository.
