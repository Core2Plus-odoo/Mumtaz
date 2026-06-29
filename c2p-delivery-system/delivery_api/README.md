# C2P delivery-api

The backbone of the C2P delivery system: one FastAPI service that runs the five
stage agents over a shared engagement, with Odoo as the system of record.

```
Presales → Proposal → Project → Functional → Developer
   └──────────────── one engagement ────────────────┘
                    delivery-api (this service)
              Claude API        Odoo (CRM → Sale → Project)
```

Each stage is an agent with its own system prompt (`prompts.py`). A stage reads
the previous stage's output off the engagement and writes its own back, so the
pipeline threads end to end without manual hand-offs. Odoo holds the records;
the agents augment standard Odoo, they never rebuild it.

## Run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
export C2P_MODEL=claude-sonnet-4-6        # set to your current model id
export ODOO_URL=http://187.77.128.199:8069
export ODOO_USER=admin
export ODOO_PASSWORD=...
uvicorn main:app --reload --port 8800
```

Interactive docs at `http://localhost:8800/docs`.

## The flow

```bash
# 1. open an engagement
curl -X POST localhost:8800/engagements \
  -H 'content-type: application/json' \
  -d '{"company":"Gulf Closets","odoo_db":"Mumtaz_ERP"}'
# -> {"id":"eng_xxx", ...}

# 2. presales (qualify + discover)
curl -X POST localhost:8800/engagements/eng_xxx/presales \
  -H 'content-type: application/json' \
  -d '{"notes":"Call summary: 120-person cabinet maker, runs on spreadsheets + QuickBooks, no shop-floor visibility, wants quotation-to-production traceability...","country":"UAE","industry":"Manufacturing"}'

# 3. proposal (reads presales automatically)
curl -X POST localhost:8800/engagements/eng_xxx/proposal -d '{}' -H 'content-type: application/json'

# 4. project (reads proposal)
curl -X POST localhost:8800/engagements/eng_xxx/project -d '{}' -H 'content-type: application/json'

# 5. functional (per requirement; installed modules auto-read from Odoo if odoo_db set)
curl -X POST localhost:8800/engagements/eng_xxx/functional \
  -H 'content-type: application/json' \
  -d '{"requirement":"Approval before any quotation above AED 50k","odoo_version":"v17"}'

# 6. developer (builds from the latest Custom-verdict functional spec)
curl -X POST localhost:8800/engagements/eng_xxx/developer -d '{"target_version":"17"}' -H 'content-type: application/json'
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/engagements` | open an engagement |
| GET | `/engagements/{id}` | full engagement state (all stage outputs) |
| POST | `/engagements/{id}/presales` | qualify + discover |
| POST | `/engagements/{id}/proposal` | scope + estimate + price |
| POST | `/engagements/{id}/project` | implementation plan |
| POST | `/engagements/{id}/functional` | requirement → verdict + spec |
| POST | `/engagements/{id}/developer` | spec → installable module |
| GET | `/odoo/{db}/modules` | installed modules (grounding) |
| GET | `/odoo/{db}/fields/{model}` | live field schema |
| POST | `/engagements/{id}/sync/lead` | write the CRM lead to Odoo |
| GET | `/health` | service + model check |

## How the frontends plug in

The static HTML consoles you've already built (functional, developer) call
these endpoints instead of the Anthropic API directly. That moves the prompt IP
server-side, lifts the browser token ceiling on the developer stage, and gives
every stage one shared engagement. The presales / proposal / project consoles
are the same pattern against `/presales`, `/proposal`, `/project`.

## Files

- `prompts.py` — the five stage system prompts (the IP).
- `models.py` — engagement + request models; in-memory `STORE` (swap for a DB).
- `odoo.py` — XML-RPC bridge: introspection + CRM/Sale/Project writes.
- `main.py` — FastAPI app wiring stages, engagement state, and the Odoo bridge.

## Persistence & Odoo write-back

Engagements persist to SQLite (`store.py`), so state survives a restart. Set the
path with `C2P_STORE` (default `delivery.db`); swap the three methods for Postgres
when you outgrow it.

Odoo is the system of record for the business objects. As each stage completes,
`sync.py` pushes its native record into Odoo's own pipeline and attaches the JSON
deliverable to it:

| Stage | Odoo record created | Attachment |
|---|---|---|
| presales | `crm.lead` | `presales.json` |
| proposal | `sale.order` (+ partner if needed) | `proposal.json` |
| project | `project.project` + `project.task` | `project_plan.json` |
| functional | (on the lead) | `functional.json` |
| developer | (on the lead) | `developer.json` |

Write-back is best-effort (an Odoo outage logs and continues, never blocks the
agent) and idempotent (created ids live on the engagement, so re-running a stage
replaces rather than duplicates). Engagements with no `odoo_db` simply skip
write-back and persist locally.

## Production notes

- For heavier reporting, add a thin `c2p_delivery` Odoo module with a
  `c2p.engagement` model (Json fields) instead of attachments — optional.
- `config-apply` (writing a "Configurable" verdict into Odoo) and module install
  remain out of scope here: install needs server/CLI access and a test run
  (Claude Code or a CI runner), not XML-RPC.
- Add auth — this is an internal operator tool; put it behind your own login.

## Files

- `prompts.py` — the five stage system prompts (the IP).
- `models.py` — engagement + request models.
- `store.py` — durable SQLite engagement store.
- `sync.py` — Odoo write-back per stage.
- `odoo.py` — XML-RPC bridge: introspection, record creation, JSON attachments.
- `main.py` — FastAPI app wiring stages, persistence, and write-back.
