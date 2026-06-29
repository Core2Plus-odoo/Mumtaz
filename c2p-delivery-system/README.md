# C2P Delivery System

Five AI agents (Presales → Proposal → Project → Functional → Developer) over one
engagement, with Odoo as the system of record. Runs on your VPS; connects to
Odoo (incl. Odoo.sh) over the API.

## Fastest path — hand it to Claude Code
1. Open Claude Code inside this folder.
2. Paste the contents of **CLAUDE-CODE-PROMPT.md** as your first message.
It will push to GitHub, deploy to the VPS at delivery.mumtaz.digital, wire Odoo,
add HTTPS, and verify — asking you for each value as it needs it.

## Manual path
Open **RUNBOOK.md** and follow the three steps. In short, on the VPS:
```bash
git clone <your-repo> c2p-delivery-system   # or upload + unzip
cd c2p-delivery-system
sudo bash deploy/setup.sh
```

## Inside
- `console/`      — the unified delivery console (one web page)
- `delivery_api/` — FastAPI backend: five agents, durable store, Odoo bridge
- `deploy/`       — installer, service, web-server config
- `CLAUDE-CODE-PROMPT.md` — the deploy brief for Claude Code
- `RUNBOOK.md`    — the manual deploy guide
- `.gitignore`    — keeps secrets out of git
