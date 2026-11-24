# 9. UI/UX design system and dashboard architecture

## 9.1 What exists [VERIFIED]

| Surface | Stack | Design language | State |
| --- | --- | --- | --- |
| Jawhar web app (`apps/jawhar-web`) | React, one `styles.css` with tokens (`--k-teal`, `--k-gold`, paper tones), EN/AR with RTL, numerals localised | Calm enterprise screens: TopBar with the approved rate, cards, worklists, tags (`ok`/`warn`/`bad`), notices, tables with `.num`; kiosk is a separate portrait teal-and-gold theme | 26 pages, every screen walked headlessly in both languages |
| Odoo web client (platform, C2P) | standard views + `mumtaz_theme` rebrand | Odoo default | no custom OWL widgets found |
| Portals and sites (under `sites/`: portal, marketplace, marketing site, ZAKI) | static HTML/JS | per site | untested |
| C2P console | single-file HTML, layered CSS passes | teal theme v4/v5 | see root `CLAUDE.md` |

## 9.2 Design system rules [PROPOSED, adopting the Jawhar conventions]

1. **One token set** (colour, spacing, type scale, radius, elevation) per product, declared once; dark mode and RTL derive from tokens, never from per-page overrides.
2. **Screen anatomy** (blueprint §11.1): global bar (company switch, search, notifications, user), role home with urgent work and approvals, list with server-side filters/sort/paging and saved views, form with state chip, approval route, primary actions, linked documents, timeline, attachments, audit.
3. **Numbers**: every money figure shows currency and the figure's origin (rate, date, engine); KPIs link to the records behind them (Jawhar owner cards and Today do this).
4. **States**: empty, loading, error with a sentence and a retry; destructive actions confirm; approvals show who and when.
5. **Accessibility**: WCAG 2.2 AA intent; keyboard reachable; labels on every input (Jawhar uses `aria-label`); RTL mirrored layouts; Arabic numerals where the language is Arabic.
6. **Density**: tables for lists, cards for decisions, chips for filters; no decorative motion (walks run with reduced motion).
7. **Odoo-side screens** stay native: list, form, kanban, pivot and graph views; custom OWL only when a native view cannot express the task (e.g. the counter).

## 9.3 Dashboard and command-centre architecture [PROPOSED]

| Audience | Screen | Source of each figure (lineage) | Status |
| --- | --- | --- | --- |
| Owner (jewellery) | Today + Decision cards | `jewellery.owner.card._desired()` reads rates, stock value at the approved rate, memos, exchanges, slow stock; each card links to its record | built |
| Group owner / CEO (C2P) | `c2p_command_center`, `c2p.dashboard` | CRM, projects, invoices; **lineage to document** | exists |
| CFO (any tenant) | standard financial reports; ZAKI board pack | `account.move.line` | custom report untested (D-02) |
| Platform admin | control-plane dashboard | subscriptions, usage, Stripe | exists |
| Sales / operations | pipeline, stores, channels (Jawhar); CRM pipeline (Odoo) | `crm.lead`, `stock.quant`, requests | built / standard |

Rules: a widget declares its domain and time filter; a figure that cannot be
drilled into is not shown; cross-company views need the explicit multi-company
permission; dashboards read, never write.

## 9.4 Next UX work (backlog items UX-01..03)

- UX-01: Odoo `mumtaz_theme` token alignment with the Jawhar palette so a group user sees one brand.
- UX-02: Metric lineage notes on the C2P command centre and the CEO dashboard.
- UX-03: Accessibility audit of the three portals (static sites) before any client-facing use.
