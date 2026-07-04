
### Premium dashboard + Sales/Customers/Project IA + project gating ✅
- **Premium dashboard** (new default home) — gradient hero with quick actions,
  four colour-coded stat tiles (Leads / Customers / Projects / Approvals), a
  recent-projects list (each bound to its customer) and a pipeline summary.
- **Separated navigation** — Sales (Leads) and Customers are now distinct
  sections; projects live under a Project section labelled with the selected
  project's name.
- **Project gating** — all project-scoped views (presales, proposal, client
  replies, documents, BA, functional, developer, execution, overview) are locked
  (🔒, dimmed) until a project is selected; clicking one routes to the Project
  Manager to open/create a project. `goView` enforces the gate too.
- **Projects bound to customers** — the dashboard shows each project's customer
  (via account_id → account name).
- Verified: JS syntax + no dup names + headless render (default=dashboard,
  sections Sales/Customers/Project, 10 gated items when no project, stat tiles
  and customer-bound project rows populate) — no page errors.

### mumtaz.digital marketing landing page ✅
Built the public marketing site the CI expected (the "Website Deployment Check"
was failing because `website/` was missing — now green).
- **`website/index.html`** — premium, responsive landing on the official
  gold-first Mumtaz brand: sticky header, hero ("The ERP — and the AI team that
  delivers it."), the two products (Mumtaz ERP + Automated ERP Implementation),
  the four segments (ERP/Bookkeeping/Accounting/Consulting), a dark how-it-works
  band (4 steps), a 6-card feature grid, a gold CTA band and footer. CTAs link to
  the console at delivery.mumtaz.digital.
- **`website/assets/css/style.css`** — self-contained gold/teal/ivory design
  system (Fraunces display + Plus Jakarta Sans), fully responsive with a mobile nav.
- **`website/assets/js/main.js`** — mobile-nav toggle, footer year, and a
  progressive-enhancement reveal (transform-only, so JS can never hide content;
  respects prefers-reduced-motion).
- Verified: JS syntax; all three CI-required files present; Playwright headless
  render (hero, both products, four segments, all sections visible) — no page
  errors.
