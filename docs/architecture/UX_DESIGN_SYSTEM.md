# Deliverable 9 — UI/UX design system and dashboard architecture

Blueprint §11. Target: a clean, high-trust enterprise experience — visually
engaging, operationally calm. Dense-data readability and fast task completion beat
decoration.

---

## 1. AS-IS: three design systems, no shared token layer

**[FACT]** Three independent palettes exist in this repository:

| System | Location | Palette |
|---|---|---|
| **Mumtaz brand** | `brand/tokens.css` + `brand/components.css` (18 KB) | Warm ivory paper `#F5F3EF`, ink `#0C1118`, **gold `#B8862A`** primary, teal `#0B7A64`, coral/blue/purple accents, full tint/border/dark ramp per hue |
| **C2P Consultants** | `addons/c2p_project_tracker/static/src/dashboard/dashboard.scss` | Charcoal `#0F0F0F`, **brand red `#BE1E2D`**, Arial, status green `#1E8E3E` / amber `#F29900` / red `#BE1E2D` / grey `#9AA0A6`, with a full dark-mode second set |
| **Agency OS console** | `c2p-delivery-system/console/c2p-delivery-console.html` | Five layered CSS passes (base → v2 polish → v3 alignment → v4 teal → v5 vibrant) |

**[FACT] They share nothing.** No token file is imported by more than one system;
there is no `--status-green` in `brand/tokens.css` and no `--gold` in the tracker.

**[DESIGN] This is correct, and it should be made explicit rather than fixed.**
Mumtaz (gold) and C2P Consultants (red) are **different brands serving different
audiences** — a SaaS platform for SMEs versus a consultancy's client-facing
delivery reporting. Collapsing them into one palette would be a branding error,
not a tidy-up. What is missing is not unification but a **declared boundary**:

```
brand/tokens.css          → Mumtaz-branded surfaces (portal, marketplace, website)
brand/tokens-c2p.css      → C2P Consultants surfaces (tracker, client PDFs)   [to create]
brand/tokens-shared.css   → spacing, radii, type scale, motion, status semantics [to create]
```

Status colours, spacing and type scale are **semantic, not brand** — they should
live in `tokens-shared.css` and be identical everywhere, because "amber means at
risk" must not change between two screens the same person uses.

## 2. The validated status palette

**[FACT]** `c2p_project_tracker`'s palette was built against a stated method:
categorical vs status palettes separated, colour-vision-deficiency ΔE validated,
contrast ≥ 3:1, dark mode as a *selected second set* rather than an algorithmic
inversion, and a glyph **plus** a label on every status so colour is never the
sole carrier of meaning.

**[DESIGN] Adopt that palette and that method as the platform status standard.**
It is already validated; re-deriving it elsewhere would be waste. The light/dark
pairs:

| Status | Light | Dark |
|---|---|---|
| On track | `#1E8E3E` | `#37A855` |
| At risk | `#F29900` | `#FFB020` |
| Critical | `#BE1E2D` | `#E0414F` |
| Inactive | `#9AA0A6` | `#96958C` |

Rule, non-negotiable (WCAG 2.2 AA, blueprint §11.2): **every status indicator
carries a glyph and a text label.** A coloured dot alone is not an indicator.

## 3. Screen anatomy

**[DESIGN]** Blueprint §11.1, adapted to Odoo's native shell. The important point
is that Odoo already provides most of this — the standard is about *not*
replacing it.

| Element | Implementation | Build or standard? |
|---|---|---|
| Global nav, company switcher, search, activities | Odoo web client | **Standard — do not replace** |
| Role home | OWL client action in the `actions` registry | Build (2 exist) |
| List view | `<list>` with server-side filters, saved views, `optional="hide"` columns | **Standard** |
| Form | Odoo form with status bar, grouped tabs, chatter, attachments | **Standard** |
| Financial detail | Explainable totals, tax breakdown, original + base currency, posting state | **Standard `account` views** |
| Exception flows | Specific validation messages from `ValidationError` | Build per constraint |
| KPI drill-down | Every tile links to an `ir.actions.act_window` with the exact domain | **Build — and mandatory** |

**The drill-down rule is the one that matters.** Blueprint §11.1: "avoid magic
totals". A KPI the user cannot click to see the records behind it is a number
they cannot trust, and it is how dashboards lose credibility permanently.
`mumtaz_financial_reports` currently fails this; `mumtaz_ceo_dashboard` is a
47-line shell that would fail it the moment it had content.

## 4. Dashboard architecture

**[FACT] Existing:** `c2p_project_tracker` ships two OWL 2 dashboards (portfolio
and delivery) reading from an `AbstractModel` payload provider
(`c2p_dashboard.py`) that calls `_check_member()` on every entry point, probes
`hours_field` against `_fields` with a `planned_hours` fallback, and **omits**
money keys rather than zeroing them for non-managers.

**[DESIGN] That is the reference architecture. Generalise it:**

```
OWL component (presentation only, no business logic)
      ↓  ORM call
AbstractModel payload provider        ← permission check here, server-side
      ↓  read_group / search_read
Authoritative domain models           ← never a separate reporting table
```

Three rules this encodes:

1. **The permission check is in the payload provider, not the component.** A
   hidden tile is not a protected tile.
2. **Restricted values are absent, not zero.** `amount: 0` is a statement about
   the business; a missing key is a statement about the viewer.
3. **No reporting tables.** Dashboards read authoritative models. A cached
   aggregate that disagrees with the ledger is worse than a slow dashboard.

### 4.1 Role dashboards to build

Blueprint §11.3. Each needs a current-period filter, a company filter, trend,
actual-vs-target, drill-through, and an **exceptions-needing-action** block —
which is the part most dashboards omit and the part users actually open them for.

| Role | Widgets | Depends on |
|---|---|---|
| Portfolio Manager | ✅ **Built** (RAG, milestones, commercials, cross-company aggregate) | needs install + run (`PRJ-002`) |
| Delivery Lead | ✅ **Built** (hygiene, blocked tasks, waiting-since) | as above |
| CFO | Cash, AR/AP ageing, bank-rec exceptions, tax position, margin | DEC-004, FIN-001 |
| CEO / Group Owner | Revenue, margin, pipeline, intercompany imbalance, data health | metric layer (`BI-001`) |
| Sales | Pipeline, conversion, discount approvals pending | L2C slice |
| Procurement | Commitments, 3-way-match exceptions, price variance | P2P slice |
| Platform Admin | Tenant health, subscription state, usage vs plan, failed webhooks | `INT-001` |

**[DESIGN] A semantic metric layer must come before the CEO dashboard**, not
after. Blueprint §11.3 requires group totals to state whether eliminations and
conversions are applied. Without a `MetricDefinition` model, two dashboards will
compute "revenue" differently and nobody will know which is right. `BI-001`.

## 5. Accessibility and localisation

**[DESIGN]** Blueprint §11.2 — WCAG 2.2 AA as the benchmark:

- Contrast ≥ 4.5:1 body text, ≥ 3:1 large text and UI boundaries. The tracker
  palette already validates; `brand/tokens.css` has **not been checked** — gold
  `#B8862A` on ivory `#F5F3EF` needs verification before it carries text.
- Keyboard-operable everything; visible focus rings (Odoo provides them — do not
  remove them in custom CSS).
- `prefers-reduced-motion` respected. The console already does this; the repo's
  `website/assets/js/main.js` uses a transform-only reveal so JS failure can
  never hide content — **that pattern should be the house rule.**
- **Arabic / RTL** is a first-class requirement for a GCC product, not a
  retrofit. Nothing in `addons/` has been RTL-tested. Any new OWL component uses
  logical properties (`margin-inline-start`, not `margin-left`) from the first
  line. `UX-001`.
- Locale-aware currency, date and number formatting via Odoo's own formatters.

## 6. PDF and print

**[FACT]** `c2p_project_tracker` ships two QWeb PDFs (Portfolio Executive Summary,
Client Status Report) designed for **wkhtmltopdf 0.12.x**, A4, avoiding
percentage bottom margins — a documented constraint, since percentage bottom
margins silently break pagination on that engine.

**[DESIGN]** Platform rules: A4 default; explicit absolute margins; brand header
and legal footer per the `c2p-group-brand` skill's unit rules; never rely on a
browser print fallback for a client-facing document. **Neither PDF has been
rendered.** `PRJ-002`.

## 7. Immediate UX actions

| ID | Action | Why |
|---|---|---|
| `UX-001` | RTL audit + logical properties in all custom CSS | GCC product; retrofit cost grows with every component |
| `UX-002` | Split `brand/tokens*.css` into shared / Mumtaz / C2P | Two brands, one semantic layer |
| `UX-003` | Contrast-check `brand/tokens.css` gold-on-ivory pairs | Unverified; used on CTAs |
| `UX-004` | Drill-down on every figure in `mumtaz_financial_reports` | Blueprint §11.1 "no magic totals" |
| `UX-005` | Decide `mumtaz_ceo_dashboard`: build on the metric layer or delete | An empty dashboard module is an invitation to put un-lineaged numbers in it |
