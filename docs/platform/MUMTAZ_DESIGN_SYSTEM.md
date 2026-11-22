# Mumtaz design system — current state and proposed single token set

Scope: brand and design tokens for the Mumtaz website, the Odoo back office,
the customer apps and white-label partners. Read-only evaluation made at
commit `2c2939a`, re-checked at `ff1c797` on 21 Nov 2026. No stylesheet,
module or site was changed by this document.

Status tags used on every row:

| Tag | Meaning |
| --- | --- |
| **VERIFIED** | Read in code at the cited path, at `ff1c797` |
| **REPORTED** | Stated in a repository document; not re-checked here |
| **PROPOSED** | Recommendation; not built; needs owner sign-off |
| **UNKNOWN** | Needs evidence from the server or a rendering test |

Related documents (not duplicated here):

- `docs/jawhar/DESIGN_SYSTEM.md` — the Jawhar design system (tokens, type, components, readiness tags)
- `docs/jawhar/WHITE_LABEL_SPECIFICATION.md` — brandable surface, data model, resolution, what is never white-labelled
- `docs/erp/UX_DESIGN_SYSTEM.md` — screen anatomy, state rules, backlog UX-01..03
- `docs/mumtaz-website/README.md` — the website module's install and test record
- `docs/erp/project/DECISION_REGISTER.md` — D-09, D-11, D-13
- `MUMTAZ_WEBSITE_IMPLEMENTATION.md` — website status and cut-over

## 1. Conclusion

**Approved direction:** deep navy foundation; emerald and lime accents; Space
Grotesk for marketing headings; Inter for application and body text; Arabic
and RTL ready; reusable tokens; white-label configurable.

**What exists:** at least six palettes and seven font pairings. Most sources
are gold-first. Only two follow the approved direction — the new website
module and the Jawhar public site — and those two disagree with each other on
the exact navy, emerald and lime. No source is a shared token file that
another one imports. The white-label brand record (`mumtaz.brand`) exists and
nothing renders it. **VERIFIED** (§2)

**Proposal:** one token set, taken from the most complete existing sheet
(`website/jewel/site/jawhar.css`), renamed product-neutrally (`--mz-*`), with
a small set of values a partner may change and everything else fixed. (§3–§6)

## 2. Brand and token sources

### 2.1 Every source

| Source | Primary colours | Fonts | Follows the direction? | Tag |
| --- | --- | --- | --- | --- |
| Approved direction | navy, emerald, lime | Space Grotesk, Inter | — | — |
| `addons/mumtaz_website_builder/static/src/css/mumtaz_builder.css:2-3` | `--mm-navy #091923`, `--mm-ink #0d202b`, `--mm-deep #0d2832`, `--mm-lime #c4f58c`, `--mm-mint #4fe0c7`, `--mm-paper #f5f7f3`, `--mm-muted #697982`; plus 104 hex literals (navy also as `#071a25`, `#0b2635`, `#102836`; emerald as `#0b332e`, `#13896f`, `#13876e`, `#158b72`, `#197862`, `#08775c`, `#16795e`; lime also as `#c5f69c`, `#d8ffa8`) | Space Grotesk, Inter (Google Fonts `@import`) | Palette and fonts yes; "reusable tokens" no | VERIFIED |
| `website/jewel/site/jawhar.css:7-33` | navy `#071A25` / `#0B2A33` / `#10363D`; emerald `#0F6B55` / `#168A6E` / `#0B4F3F`; lime `#C5F69C` / `#D8FFA8`; teal `#1ABC9C`; gold `#C4A464`; sapphire `#102C48`; aubergine `#482655`; paper `#F4F7F5`; ink `#0B1F2A`. Dark mode, spacing scale, radii, two shadows, focus ring | Space Grotesk, Inter; declares IBM Plex Sans Arabic (`:25`) but the page does not load it (`website/jewel/index.html:17`) | Yes — most complete | VERIFIED |
| `docs/jawhar/DESIGN_SYSTEM.md` §2 | Same table, except ink `#14202B / #2D3B4A / #5E6B7A / #8A96A3` and dark ink `#F2EEE6`, which differ from the CSS (`#0B1F2A / #2A3B45 / #5C6E76 / #8A9AA2`, dark `#F2F6F3`). Also says control radius 10; CSS has 9 | Same | Document and CSS disagree | VERIFIED |
| `apps/jawhar-web/src/styles.css:6-15` | ivory paper `#F7F3EC`; `--gold` is actually emerald `#0F6B55`; accent gold `#C4A464`; rail `#0B1B2B`; ink `#14202B` | Plus Jakarta Sans, Cormorant Garamond, IBM Plex Sans Arabic (loaded, `apps/jawhar-web/index.html:10`) | Partly | VERIFIED |
| `docs/design/brand-tokens-v3/tokens.css:8-88` | gold `#B8862A` primary; teal `#0B7A64`; paper `#F5F3EF`; ink `#0C1118` | Instrument Serif, DM Sans, DM Mono | No (gold-first). Nothing imports it | VERIFIED |
| `addons/mumtaz_theme` | `--o-brand-primary #B8862A` (`static/src/css/mumtaz_backend.css:8,19`); logo and favicon SVGs use blue `#1a73e8` | DM Sans, Instrument Serif, DM Mono, forced with `!important` on `body` through `web.layout` (`views/webclient_templates.xml:14-22`) | No | VERIFIED |
| `addons/mumtaz_branding/models/mumtaz_brand.py:32-39` | defaults `#0f3460` / `#16213e` | none | No. No reader of `primary_color` or `secondary_color` exists outside the module | VERIFIED |
| `addons/mumtaz_website/static/src/css/website.css:7-14` | background `#060b14`; gold `#f0a500` / `#fbbf24`; blue `#3b82f6` | Inter | No | VERIFIED |
| `sites/mumtaz.digital/site/assets/css/tokens.css` | gold `#B8862A`; teal `#0B7A64`; paper `#FAF8F4`; ink `#1C1917` | Inter, DM Mono | No | REPORTED |
| `sites/mumtaz.digital/site/index.html` (inline) | background `#05050D`; gold `#F59E0B` / `#FCD34D` / `#D97706`; teal `#14B8A6` | Inter, DM Mono | No | REPORTED |
| `sites/delivery.mumtaz.digital/landing/assets/css/style.css` | paper `#F5F3EF`; ink `#0C1118`; gold `#B8862A`; teal `#0B7A64` | Fraunces, Plus Jakarta Sans | No | REPORTED |
| `platform/marketing/index.html` | paper `#FAF8F4`; ink `#1C1917`; gold `#B8862A`; green `#0B7A64`; mark "م" | Inter, DM Mono | No. `platform/README.md:7-8` records this as an owner decision ("ivory/gold/Inter, not teal/navy") | VERIFIED (README), REPORTED (values) |
| `mumtaz_organization`, `mumtaz_customer_portal`, `mumtaz_vendor_portal`, `sites/app.mumtaz.digital/portal` | gold-first | Instrument Serif, DM Sans | No | REPORTED |
| `faizy/brand/README.md` | orange `#F69E22`; black `#0A0A0A` | Poppins, Noto Nastaliq Urdu | Separate product; out of scope | REPORTED |

### 2.2 Disagreements

| # | Disagreement | Tag |
| --- | --- | --- |
| 1 | **Primary colour:** gold in most sources; emerald and lime in the website module and the Jawhar site | VERIFIED |
| 2 | **Gold itself:** three values (`#B8862A`, `#f0a500`, `#F59E0B`) | VERIFIED / REPORTED |
| 3 | **Paper and ink inside the gold family:** `#F5F3EF` + `#0C1118` versus `#FAF8F4` + `#1C1917` | VERIFIED / REPORTED |
| 4 | **The two sources that follow the direction differ:** navy `#091923` vs `#071A25`; lime `#c4f58c` vs `#C5F69C`; emerald (seven literals vs a three-step ramp) | VERIFIED |
| 5 | **Jawhar document vs Jawhar CSS:** ink scale and control radius | VERIFIED |
| 6 | **Logo mark:** blue in `mumtaz_theme`; gold "م" in `platform/marketing` | VERIFIED / REPORTED |
| 7 | **Recorded decision vs new direction:** `platform/README.md:7-8` records ivory/gold/Inter; the approved direction supersedes it, and decision D-13 ("choose one brand source") is still open | VERIFIED |
| 8 | **Fonts:** seven pairings; three different Arabic situations (declared and not loaded; loaded; absent) | VERIFIED |

## 3. Proposed single token set

**PROPOSED — pending owner sign-off.** Values are taken from
`website/jewel/site/jawhar.css:7-52` as it stands at `ff1c797`, not invented.
Where the Jawhar document and the CSS disagree, the CSS value is used (it is
what renders). Names are product-neutral so Mumtaz, Jawhar, Pharma and a
partner brand can share them.

### 3.1 Colour

| Token | Light | Dark | Source token | Role |
| --- | --- | --- | --- | --- |
| `--mz-navy` / `-2` / `-3` | `#071A25` / `#0B2A33` / `#10363D` | same | `--navy*` | Foundation: hero, dark bands, navigation rail, table heads |
| `--mz-emerald` / `-2` / `-deep` | `#0F6B55` / `#168A6E` / `#0B4F3F` | `#2FB48F` / `#5CCBAD` / `#1E8C6E` | `--emerald*` | Primary action on light, links |
| `--mz-emerald-soft` / `-line` | `#E6F2EE` / `#BFD9CF` | `#163528` / `#2A5A47` | same | Tinted backgrounds, borders |
| `--mz-lime` / `-2` | `#C5F69C` / `#D8FFA8` | same | `--lime*` | Primary action and emphasis **on dark only** |
| `--mz-lime-ink` | `#2F5A12` | same | `--lime-ink` | Lime-family text on light |
| `--mz-teal` / `-ink` / `-soft` | `#1ABC9C` / `#0E8C78` / `#E3F6F1` | — / `#5ED9BE` / `#0F2F2A` | `--teal*` | Focus ring, informational state |
| `--mz-paper` / `-2` | `#F4F7F5` / `#EAF0EC` | `#071A25` / `#0B2A33` | `--paper*` | Page ground |
| `--mz-surface` | `#FFFFFF` | `#0B2A33` | `--surface` | Cards, inputs |
| `--mz-line` | `#D9E3DD` | `#1C3A41` | `--line` | Hairlines |
| `--mz-ink` / `-2` / `-3` / `-4` | `#0B1F2A` / `#2A3B45` / `#5C6E76` / `#8A9AA2` | `#F2F6F3` / `#D5DEDC` / `#9FB3B3` / `#6F8588` | `--ink*` | Text, strongest to faintest |
| `--mz-on-dark` / `-2` | `#F4F7F5` / `#B7C9C9` | same | `--on-dark*` | Text on navy |
| `--mz-danger` / `-soft` | `#B42318` / `#FDECEA` | — / `#2E1512` | `--coral*` | Errors |

Edition accents stay with the edition and are not part of the shared set:
Jawhar keeps gold (`--gold #C4A464` and its ramp), sapphire and aubergine
(`jawhar.css:10-12`). **PROPOSED**

Semantic status colours (warning, information, success with background and
border) are not complete in the Jawhar sheet. Take the families from
`docs/design/brand-tokens-v3/tokens.css:43-66` (coral, blue, purple, amber, each with `-bg` and
`-border`) and re-check their contrast against `--mz-paper`. **PROPOSED**

Contrast of the proposed pairs, computed for this document with the WCAG 2.x
formula:

| Foreground on background | Ratio | Usable for body text (≥ 4.5:1)? |
| --- | --- | --- |
| `--mz-ink` on `--mz-paper` | 15.7:1 | Yes |
| `--mz-ink-2` on `--mz-paper` | 10.8:1 | Yes |
| `--mz-ink-3` on `--mz-paper` | 4.9:1 | Yes |
| `--mz-ink-4` on `--mz-paper` | 2.7:1 | **No** — decoration and disabled state only |
| `--mz-emerald-deep` on `--mz-paper` | 8.8:1 | Yes |
| white on `--mz-emerald` (button) | 6.5:1 | Yes |
| `--mz-lime` on `--mz-navy` | 14.4:1 | Yes |
| `--mz-on-dark` on `--mz-navy` | 16.5:1 | Yes |
| `--mz-on-dark-2` on `--mz-navy` | 10.3:1 | Yes |
| `#10261D` on `--mz-lime` (button label) | 12.9:1 | Yes |
| `--mz-lime` on white | 1.2:1 | **No** — never lime text or lime controls on a light ground |
| `--mz-lime-ink` on `--mz-paper` | 7.5:1 | Yes |
| `--mz-danger` on `--mz-paper` | 6.1:1 | Yes |
| dark `--mz-ink` on dark `--mz-paper` | 16.3:1 | Yes |
| dark `--mz-emerald` on dark `--mz-paper` | 6.8:1 | Yes |

These differ from the figures printed in `docs/jawhar/DESIGN_SYSTEM.md` §2
(13.5:1 and 7.6:1) because that document lists a different ink value than
the CSS (§2.2 row 5).

### 3.2 Type

| Token | Value | Source | Tag |
| --- | --- | --- | --- |
| `--mz-font-display` | `'Space Grotesk','Inter',system-ui,-apple-system,'Segoe UI',sans-serif` | `jawhar.css:23` | PROPOSED |
| `--mz-font-body` | `'Inter',system-ui,-apple-system,'Segoe UI',sans-serif` | `jawhar.css:24` | PROPOSED |
| `--mz-font-arabic` | `'IBM Plex Sans Arabic',system-ui,sans-serif` | `jawhar.css:25` (drop the Plus Jakarta Sans fallback, which has no Arabic glyphs to offer) | PROPOSED |
| Display use | Marketing headings h1 and h2 only: weight 700, tracking −0.045em, line-height 1.05 | `jawhar.css:60` | PROPOSED |
| h1 / h2 size | `clamp(2.6rem,5.8vw,4.6rem)` / `clamp(1.9rem,3.4vw,2.8rem)` | `jawhar.css:61-62` | PROPOSED |
| h3 / h4 | 1.12rem / 0.95rem, weight 700, Inter | `jawhar.css:63-64` | PROPOSED |
| Body | Inter 16px, line-height 1.7 (marketing); application screens may use 1.5 | `jawhar.css:57` | PROPOSED |
| Small / eyebrow | 0.82rem; eyebrow 0.72rem, weight 800, tracking 0.16em, uppercase | `jawhar.css:73,75` | PROPOSED |
| Numerals | `font-variant-numeric: tabular-nums` on every figure | `jawhar.css:74` | PROPOSED |
| Application screens | Inter only. Space Grotesk is not used inside the ERP or the apps | Approved direction | PROPOSED |

Fonts are self-hosted with the product, not requested from a third-party host,
so a bank-controlled or data-residency deployment needs no exception. Today
every source loads from Google Fonts. **PROPOSED**

### 3.3 Space, shape, depth, focus

| Token | Value | Source | Tag |
| --- | --- | --- | --- |
| `--mz-s1` … `--mz-s9` | 4, 8, 12, 16, 24, 32, 48, 72, 104 px | `jawhar.css:32` | PROPOSED |
| `--mz-radius` / `-sm` / `-pill` | 14px / 9px / 999px | `jawhar.css:27` | PROPOSED |
| `--mz-shadow` | `0 1px 2px rgba(20,32,43,.05), 0 2px 6px rgba(20,32,43,.06)`; dark: `0 1px 2px rgba(0,0,0,.35), 0 8px 24px rgba(0,0,0,.35)` | `jawhar.css:28,42` | PROPOSED |
| `--mz-shadow-lg` | `0 12px 40px rgba(16,44,72,.14)`; dark: `0 16px 48px rgba(0,0,0,.5)` | `jawhar.css:29,42` | PROPOSED |
| `--mz-ring` | `0 0 0 3px rgba(26,188,156,.35)` on `:focus-visible` for links, buttons and form controls | `jawhar.css:30,67` | PROPOSED |
| `--mz-wrap` | 1230px content width | `jawhar.css:27` | PROPOSED |

### 3.4 Light and dark

Dark mode follows `prefers-color-scheme` unless `data-theme="light"` is set,
and can be forced with `data-theme="dark"` (`jawhar.css:34-52`). Navy, lime
and on-dark tokens do not change between modes. The theme is applied before
first paint (the Jawhar app already does this). **PROPOSED**

## 4. White-label

### 4.1 Resolution path

Host → tenant → brand record → tokens (`docs/jawhar/WHITE_LABEL_SPECIFICATION.md` §3).

| Step | Today | Tag |
| --- | --- | --- |
| Host → tenant | `mumtaz.tenant.subdomain` / `custom_domain`; routing in `mumtaz_subdomain_routing` (off by default) | VERIFIED |
| Tenant → brand | `mumtaz.tenant.brand_id` → `mumtaz.brand` | VERIFIED |
| Brand → tokens | **Missing.** `mumtaz.brand` stores a logo, favicon and two colours; no code reads `primary_color` or `secondary_color` outside `mumtaz_branding` | VERIFIED |
| Tokens → screen | **Missing.** `mumtaz_theme` ships fixed CSS; the website module ships fixed hex values | VERIFIED |

Proposed: the brand record is the only place a partner's values live. A small
renderer turns it into a block of `--mz-*` overrides (served with the login
page, the app shell and the website layout, cached per tenant, invalidated on
write). A missing brand falls back to the Mumtaz defaults in §3. **PROPOSED**

### 4.2 What a partner may change, and what is fixed

| A partner may change | Fixed for everyone |
| --- | --- |
| Product name (Latin and Arabic) | Spacing, radius and elevation scales |
| Logo and favicon | Component anatomy and screen anatomy (`docs/erp/UX_DESIGN_SYSTEM.md` §9.2) |
| Primary colour and one accent colour, within the contrast rule below | Semantic status colours (danger, warning, information, success) |
| One of a few curated font pairs | Focus ring and all accessibility rules (§5) |
| Login background and tagline | Readiness vocabulary (built / staging / planned) |
| E-mail sender name and footer | Consent wording (translation allowed, meaning fixed) |
| Report header and footer | Pricing engine, autonomy policy and audit trail behaviour (`docs/jawhar/WHITE_LABEL_SPECIFICATION.md` §5) |
| Kiosk assistant name; domain | |

Contrast rule for partner colours: the primary colour on white must reach
4.5:1 or the save is refused with the computed ratio
(`docs/jawhar/WHITE_LABEL_SPECIFICATION.md` §2). The same check applies to
the label colour on the primary colour. **REPORTED as specification; not built**

All of this table is **PROPOSED**; it restates the Jawhar specification for
the whole platform.

## 5. RTL, Arabic and accessibility rules

All **PROPOSED** as platform rules; the sources that already follow each one
are cited.

| Rule | Already followed by | Not followed by |
| --- | --- | --- |
| Layout uses CSS logical properties (`margin-inline-start`, `padding-inline`, `inset-inline-*`, `text-align: start`); no physical left/right in new code | `apps/jawhar-web/src/styles.css:36,62` (VERIFIED: `[dir=rtl]` rules and logical properties) | `mumtaz_builder.css`: 13 physical declarations, 0 logical (VERIFIED) |
| An Arabic font is actually loaded wherever `lang="ar"` or `dir="rtl"` can occur | `apps/jawhar-web/index.html:10` (VERIFIED) | Jawhar site declares it but does not load it; the website module has none (VERIFIED) |
| `[lang="ar"], [dir="rtl"]` switch the font family | `jawhar.css:58` (VERIFIED) | website module (VERIFIED) |
| No negative letter-spacing and no uppercase tracking on Arabic text; reset both under `[lang="ar"]` | — | `mumtaz_builder.css` (−.04 to −.07em on headings) and `jawhar.css:60` apply negative tracking with no Arabic reset (VERIFIED) |
| Arabic numerals where the language is Arabic; tabular figures everywhere | `docs/jawhar/DESIGN_SYSTEM.md` §1 (REPORTED) | — |
| Directional icons and arrows mirror in RTL | — | website module uses literal "↗" and "↓" characters (VERIFIED) |
| Text contrast ≥ 4.5:1 (3:1 for text ≥ 24px or bold ≥ 18.66px); check before using a brand colour as text | §3.1 table | Not checked in any gold-first source (UNKNOWN) |
| Visible focus on every interactive element (`--mz-ring`) | `jawhar.css:67` (VERIFIED) | `mumtaz_builder.css` has no `:focus` rule (VERIFIED) |
| `prefers-reduced-motion: reduce` removes animation, transition and smooth scroll | `jawhar.css:191-195`; `mumtaz_builder.css` has one such rule (VERIFIED) | — |
| Skip link, labelled inputs, keyboard reachability; WCAG 2.2 AA intent | `jawhar.css:70-71`; `docs/erp/UX_DESIGN_SYSTEM.md` §9.2 rule 5 | Portals: audit pending (backlog UX-03) |
| Odoo websites: Arabic needs `rtlcss` on the server to generate the RTL bundle | — | Whether it is installed: UNKNOWN |

How the website page looks in Arabic has not been rendered anywhere. **UNKNOWN**

## 6. What to take, what to retire, and in what order

### 6.1 From each source

| Source | Take | Leave / retire | Tag |
| --- | --- | --- | --- |
| `website/jewel/site/jawhar.css` + `docs/jawhar/DESIGN_SYSTEM.md` | The base token set (§3), dark mode, spacing, radii, shadows, focus ring, tabular numerals, skip link, reduced-motion rule, readiness tags, imagery policy | Fix the ink and radius mismatch between the document and the CSS; keep gold, sapphire and aubergine as Jawhar edition accents | PROPOSED |
| `addons/mumtaz_website_builder` | The marketing section patterns (hero with product frame, path cards, module tiles, edition band, AI panel, partner panel, form card, eyebrow and button styles) | Rewrite the stylesheet on `--mz-*`: remove the 104 hex literals and the four unused variables; add focus, RTL and logical properties | PROPOSED |
| `docs/design/brand-tokens-v3/tokens.css`, `docs/design/brand-tokens-v3/components.css` | Semantic status families with background and border; transition scale; the application component inventory (buttons, input, card, badge, status dot, sidebar, top bar, KPI card, modal, toast, table wrapper) | Gold as primary; the serif pairing. Retire the files once their components are re-expressed on `--mz-*` | PROPOSED |
| `apps/jawhar-web` | RTL through logical properties; loaded Arabic font; theme applied before first paint | Its ivory paper and the misnamed `--gold` (which holds emerald) once it adopts the shared names | PROPOSED |
| `addons/mumtaz_theme` | The technique for rebranding the Odoo back office and login (`--o-brand-primary`, login layout) | Gold values, DM Sans / Instrument Serif, the blue logo and favicon, and the `!important` font rule injected through `web.layout` (it also reaches website pages on the same database) | PROPOSED |
| `addons/mumtaz_branding` + `docs/jawhar/WHITE_LABEL_SPECIFICATION.md` | The partner brand record and the resolution path; the contrast check | Its default colours `#0f3460` / `#16213e` | PROPOSED |
| `docs/erp/UX_DESIGN_SYSTEM.md` §9.2 | Screen anatomy and state rules | — | PROPOSED |
| `addons/mumtaz_website` | Nothing visual | Retire after cut-over (`MUMTAZ_WEBSITE_IMPLEMENTATION.md` §3) | PROPOSED |
| Static sites (`sites/mumtaz.digital/site`, `website/`, `platform/marketing`) | Copy and page inventory only | Their palettes | PROPOSED |
| `faizy/brand` | Only its Urdu / RTL rendering rules and "check contrast before using a brand colour as text" | Never its palette; it is a separate product | PROPOSED |

### 6.2 Migration order

Each step is reversible and ships on its own. None has been started.

| # | Step | Why this order | Done when |
| --- | --- | --- | --- |
| 0 | Owner signs off §3 and closes D-13 (one brand source) | Everything below depends on the values | Decision recorded in `docs/erp/project/DECISION_REGISTER.md` |
| 1 | **Website tokens first.** One `--mz-*` token file; `mumtaz_website_builder` rewritten on it; fonts self-hosted; focus, RTL and logical properties added | Smallest surface, already on the approved palette, unpublished, tested | Module tests pass; no hex literal outside the token file; page renders correctly in English and Arabic on staging |
| 2 | Align the Jawhar site and `docs/jawhar/DESIGN_SYSTEM.md` to the same names and values (edition accents kept) | Removes the navy / lime / ink differences between the two sources that already agree in spirit | Jawhar CI green; document and CSS show the same values |
| 3 | **Re-token `mumtaz_theme`** (backlog UX-01): `--o-brand-primary` and the login page from `--mz-*`; remove the forced DM Sans; new logo and favicon | Back office is the largest audience; needs a staging database per instance first | Screens reviewed on staging for each instance that has the module installed (which instances: UNKNOWN) |
| 4 | Brand renderer: `mumtaz.brand` → `--mz-*` overrides, with the contrast check | Makes the tokens white-label configurable; depends on 1 and 3 | The acceptance case in `docs/jawhar/WHITE_LABEL_SPECIFICATION.md` §6 passes |
| 5 | **Apps:** `apps/jawhar-web`, the customer and vendor portals, `mumtaz_organization`, the app portal | Largest and most varied; do after the tokens are proven | Each app imports the token file; accessibility audit UX-03 done |
| 6 | Retire `docs/design/brand-tokens-v3/tokens.css`, `docs/design/brand-tokens-v3/components.css`, the static sites' palettes and `mumtaz_website` | Only after nothing reads them | One pull request per retirement |

## 7. Could not determine

- Whether Space Grotesk and Inter actually render on the website page (never
  confirmed: `docs/mumtaz-website/README.md:74`).
- How any page looks in Arabic; whether `rtlcss` is on the server.
- Which databases have `mumtaz_theme` installed, and therefore who is affected
  by step 3.
- Whether Odoo Website Builder colour presets override the module's colours.
- Contrast of the gold-first sources (not computed; they are to be retired).
- Whether the owner has signed off the exact navy, emerald and lime values;
  the two conforming sources differ (§2.2 row 4).
