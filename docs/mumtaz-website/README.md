# Mumtaz Digital website — native Odoo 19 Website Builder module

Module: `addons/mumtaz_website_builder`. Delivered against the Website
Implementation Directive of 21 Nov 2026. This file is the install guide, the
test record, the list of issues corrected and the production checklist.

## 1. What the module is

- Seven Website Builder blocks under **Blocks → Mumtaz Digital**: Hero, Three
  Visitor Paths, ERP Highlights (eight module tiles), Industry Editions, ZAKI
  AI Showcase, White-Label Partners, Native CRM Demo Form.
- One **unpublished** page at `/mumtaz-native-preview`, assembled from those
  blocks inside the standard `website.layout`, so the site's own header,
  footer, menus, SEO fields, translations and the Edit button apply.
- A native Website Form on `crm.lead` with contact name, business name,
  business e-mail, phone, interested solution (CRM tag), message and a
  required privacy consent. Submission is accepted only by the server; the
  success message is shown by Odoo after a 200 response.
- Four `crm.tag` records (Mumtaz ERP, Industry solution, White-label ERP,
  ZAKI AI) and a whitelist entry so the form may set `tag_ids`.
- CSS scoped to `.o_mumtaz_site`; nothing applies to other websites on the
  same database. Fonts Space Grotesk and Inter via Google Fonts.
- Installation changes nothing visible: no homepage, no menu, no published
  page.

## 2. Inspection of the environment (what could and could not be checked)

| Item | Result |
| --- | --- |
| Odoo version | Odoo 19 Community (sandbox from the repository's CI), same major as production |
| Mumtaz website / `website_id` on production | **Not inspectable from here** (no server access). The module does not set `website_id`; the administrator assigns the page to the Mumtaz website after install (checklist §6) |
| Installed website modules on production | Not inspectable; `website`, `website_crm` are standard and auto-installed by this module's dependencies |
| Existing custom website code in the repo | `mumtaz_website` (controller-rendered pages at `/mumtaz/*`, own navbar) and `mumtaz_theme` (backend/login rebrand). Neither conflicts technically with this module (different routes, templates and assets). `mumtaz_website` is marked superseded in `registry/classification.json` and is left installed-or-not as it is |
| Production `mumtaz.digital` | Served as static HTML by nginx (`platform/ops/nginx/mumtaz.digital.conf`, root `/opt/mumtaz/marketing`); Odoo answers on `app.`/`erp.` hosts. Cutting the apex domain over to the Odoo website is a separate, approved infrastructure change (§6) |

## 3. Issues found in the attached module and corrected

| # | Issue | Effect | Fix |
| --- | --- | --- | --- |
| 1 | `@import url('…css2?family=Inter:wght@400;500…')` in the module CSS | Odoo's bundler hoists `@import` rules with a regex that stops at the first `;`, so the rule was cut inside the URL and the **entire frontend stylesheet became invalid: the whole website rendered unstyled** (reproduced on a fresh database) | Use the Google Fonts v1 URL (`css?family=Inter:400,…|Space+Grotesk:…`, no semicolons). A test now asserts the bundle still contains Odoo's footer rules after ours |
| 2 | Jawhar illustration not constrained | 284 px horizontal overflow on a 390 px phone | `.o_mumtaz_site img{max-width:100%;height:auto}` |
| 3 | Form missing phone, interested solution and consent (directive §7) | Leads without phone or intent; no consent record | Added native fields; solution writes a CRM tag (whitelisted), consent goes into the lead description as "Privacy consent : Yes" via Odoo's custom-field mechanism; business name now required |
| 4 | Section padding 90–108 px, 5.3 screens tall | Excessive scrolling (directive §4) | Padding 56–72 px desktop, 48 px on phones |
| 5 | ERP block listed three generic bullets | Directive §5 asks for the business modules | Eight tiles: Finance, Sales, CRM, Procurement, Inventory, HR, Operations, ZAKI AI |
| 6 | Edition statuses "Product website / Proposed" | Available vs planned not distinct | "● Available" (Jawhar) and "◌ Planned" (Pharma, Retail & distribution) |
| 7 | Page markup duplicated the block markup by hand | The two drift apart over time | The page arch is regenerated from the blocks file by the build step used in this slice; keep doing that when blocks change |
| 8 | No tests | Runtime behaviour was declared "not validated" in the README | Six HTTP tests (install footprint, admin render, builder registration, stylesheet integrity, form success, form refusal) |
| 9 | Copy: hero CTAs and pathway headings | Did not match the directive's wording | "Book a demo", "Explore solutions", "Choose your solution", "Run my business / Find my industry / Offer ERP under my brand" |
| 10 | Every two-column section stacked at desktop width | Odoo's theme adds clearfix `::before/::after` on `.container`; inside a CSS grid they become phantom first items, so the copy landed in column two and the visual on the next row | `#wrap .o_mumtaz_site .container::before/::after{content:none}`; covered by the stylesheet test |
| 11 | Form had no `#s_website_form_result` element | Odoo's form script crashed with an error dialog the moment it tried to show any status (so a server refusal could never be displayed) | Native submit-row markup restored; covered by test |
| 12 | Server accepted posts with no contact, e-mail or consent | Odoo only enforces model-required fields server side; a bot posting directly would create empty leads | Scoped controller override for this one form (by its fixed subject): required fields, e-mail format, phone length, honeypot, size cap; message returned to the form |
| 14 | Same `css2` import defect found in `mumtaz_organization` (frontend bundle) while running the whole-platform install | Any database with that module installed served an unparsable frontend stylesheet, so the website rendered unstyled | Same one-line URL fix in that module; the stylesheet test now checks that every hoisted `@import` in the bundle is a complete rule, whichever module contributed it |
| 13 | (introduced and removed during this work) QWeb `t-att` inside the page wrap | Odoo could not brand `#wrap` as one editable structure; every block group showed "cannot be dropped on this page" | Markup kept literal; the chosen solution travels as text and the controller maps it to the CRM tag; a test forbids directives inside the wrap |

## 4. Test results (fresh Odoo 19 database, `website` + `website_crm` + this module, 21 Nov 2026)

| Check | Result |
| --- | --- |
| Install on an empty database (no demo data) | OK, no errors |
| `odoo --test-enable --test-tags /mumtaz_website_builder` | **7 tests, 0 failed, 0 errors** |
| flake8, pyflakes, `scripts/check_sudo.py` | clean |
| Headless render as administrator at 1440 / 834 / 390 px | 200, 7 sections, 0 px horizontal overflow at every width, 0 console errors, hero styled (navy) |
| Page height | 5.3 screens desktop, 4.8 tablet, 9.5 phone |
| Visitor (not logged in) | 404 on the unpublished page, as required |
| Website Builder on the page | `#wrap` branded and editable; **all block groups enabled** incl. "Mumtaz Digital"; seven blocks listed in the group dialog |
| Browser form submission | Empty form blocked by the browser; completed form: `POST /website/form/crm.lead` → 200 `{"id": …}`; success message shown only after the response; lead carries contact, business, e-mail, phone, tag *Industry solution*, message, and the lines "Interested solution : …" and "Privacy consent : Yes" |
| Server-side refusal | Posts without name, e-mail, business, solution or consent, with a short phone, or with the honeypot filled are refused with a message and create nothing; other website forms on the database are unaffected (test) |
| Multi-website isolation | Every rule is scoped to `.o_mumtaz_site`; nothing targets `body`, `#wrap` globally, header or footer (reviewed) |
| Fonts | Google Fonts request is well-formed in the bundle; glyph rendering of Space Grotesk/Inter could not be confirmed in the sandbox (no outbound fonts network) — check visually on staging |

Screenshots: `docs/mumtaz-website/screenshots/` (desktop, tablet, phone, form
success, builder blocks tab, builder Mumtaz group).

## 5. Installation and upgrade

Install (staging first):

```bash
# addons path already contains /opt/<checkout>/addons
odoo -d <database> -i mumtaz_website_builder --stop-after-init
```

Upgrade:

```bash
odoo -d <database> -u mumtaz_website_builder --stop-after-init
```

Upgrade updates the seven block templates and the stylesheet. The preview
page record is `noupdate`, so a page already edited in the Website Builder
keeps its content; to receive the new page layout on an existing database,
delete the preview page (Website → Pages) before upgrading, or rebuild it from
the blocks in the editor.

## 6. Production deployment checklist (each step needs a named approval)

1. Install on the staging database of the Mumtaz website; confirm the page renders and the builder shows the block group.
2. In Website → Pages, set the preview page's **Website** to the Mumtaz website (multi-website database) and keep it unpublished.
3. Set the company logo, header menu and footer through the Website editor (the module does not touch them).
4. Configure anti-spam: install `website_cf_turnstile` (standard, Odoo 19 CE) and enter the Cloudflare site and secret keys in Website settings, or reCAPTCHA. Submit one synthetic request and confirm the lead appears under CRM with the tag and the consent line; delete it.
5. Review SEO fields (title, description, image) on the page; translations if Arabic is enabled.
6. Publish the page; add it to the menu; then, and only then, set it as the website homepage (Website → Pages → Set as homepage).
7. Domain: point `mumtaz.digital` at the Odoo website host (the current static site is served by nginx from `/opt/mumtaz/marketing`); keep the static site until the Odoo page is approved; redirect old static URLs that still receive traffic.
8. Keep a database backup from before step 6; rollback is "unset homepage, unpublish page, restore nginx static site".

## 7. Remaining limitations

- Not run on the actual production or staging server: no server access from this session. Everything below "Test results" comes from a fresh sandbox database.
- Fonts load from Google Fonts for every page of every website on the database that includes the frontend bundle (this is how Odoo's own theme loads Inter too). For data-residency, host the two families locally and change the `@import`.
- Spam protection relies on Odoo's captcha hook (`website_cf_turnstile` or reCAPTCHA) being configured; the module itself adds none beyond required fields and server-side validation.
- Dashboard numbers, the ZAKI conversation and the partner mock-up are illustrative and labelled as such; replace before publication if real figures are wanted.
- Block thumbnails are simple SVG placeholders.
- The page is English only; translations are entered through Website → Translate once the content is final.
