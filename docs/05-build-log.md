
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
