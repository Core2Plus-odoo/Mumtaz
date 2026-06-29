# Architecture (summary)

- **api/** — FastAPI backbone (`delivery-api`): one service, one endpoint per agent,
  shared engagement state, durable store, Odoo bridge. The agent system prompts in
  `api/prompts.py` are the core IP.
- **console/** — operator UI(s), static HTML on Nginx.
- **Odoo** — system of record (CRM lead → Sales order → Project), reached over
  XML-RPC; custom modules deploy via the relevant addons repo / Odoo.sh.
- **State** — durable store (SQLite now → Postgres for the product), plus the
  per-client knowledge base.

Multi-tenant target: shared control plane + per-tenant data isolation for client
knowledge. See 03-productization-and-organization.md.
