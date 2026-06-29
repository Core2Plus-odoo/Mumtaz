# Task for Claude Code — deploy the C2P Delivery System

You are deploying an existing, tested codebase to production. Do **not** rebuild
it from scratch — work with the files in this folder. Read them first, then
execute the steps below, asking me for any value you need. Never hardcode or
commit a secret.

---

## What this is

The **C2P Delivery System** — an end-to-end Odoo delivery pipeline of five AI
agents (Presales → Proposal → Project → Functional → Developer) that run over one
shared "engagement", with Odoo as the system of record. The codebase in this
folder:

```
c2p-delivery-system/
├── console/c2p-delivery-console.html   # the single-page UI (calls /api/…)
├── delivery_api/                       # FastAPI backend
│   ├── main.py        # endpoints: /engagements, /…/presales … /…/developer, /odoo/…, /health
│   ├── prompts.py     # the five stage system prompts
│   ├── store.py       # durable SQLite engagement store
│   ├── sync.py        # writes each stage back to Odoo (lead → quotation → project + JSON attachments)
│   ├── odoo.py        # XML-RPC bridge (introspection + record creation)
│   ├── models.py, requirements.txt, README.md
├── deploy/
│   ├── setup.sh                    # idempotent installer (venv, systemd, nginx, login gate)
│   ├── delivery-api.service.tmpl   # systemd unit template
│   └── nginx-delivery.conf.tmpl    # nginx site template (serves console at /, proxies /api/ → 127.0.0.1:8800)
├── .gitignore, README.md, RUNBOOK.md
```

**Start by reading** `README.md`, `delivery_api/README.md`, `deploy/setup.sh`, and
`deploy/nginx-delivery.conf.tmpl` so you understand the moving parts before touching anything.

## Objective / definition of done

`https://delivery.mumtaz.digital` loads behind a login over HTTPS; `/api/health`
returns ok; and a test engagement's **Presales** run creates a `crm.lead` in my
Odoo.sh database. The repo is pushed to GitHub with **no secrets committed**.

## Environment

- **Host:** my Hostinger KVM 2 VPS, Ubuntu 24.04. (Ask me for SSH access, or you
  may be running on the VPS already — confirm which.)
- **Domain:** `delivery.mumtaz.digital`, a subdomain of `mumtaz.digital`.
- **Odoo:** an **Odoo.sh** instance, reached over its XML-RPC external API at the
  instance URL. The GitHub repo is *not* the Odoo connection — the connection is
  four values in `delivery_api/.env`.
- **GitHub:** org `Core2Plus-odoo`. Create/use a repo (I'll give the name).

## Steps — do in order

1. **Understand the package.** Read the files listed above. Note that
   `deploy/setup.sh` already handles the Python venv, the `delivery-api` systemd
   service (uvicorn on `127.0.0.1:8800`), the nginx site, and an HTTP basic-auth
   login gate, and that it's idempotent (safe to re-run).

2. **Git + GitHub.** Initialise git if needed. Verify `.gitignore` excludes
   `delivery_api/.env`, `.htpasswd`, `delivery_api/delivery.db`, `.venv/`, `web/`.
   Create the repo under `Core2Plus-odoo` (ask me for the name; use `gh` if
   available) and push `main`. Confirm no secret files are tracked
   (`git ls-files | grep -E '\.env|htpasswd|\.db'` must be empty).

3. **Odoo bot user (my manual step — guide me).** Tell me to, in Odoo:
   create a user `C2P Delivery Bot` with access to **Sales, CRM, Project** and
   **Administration → Settings**, then generate an **API key** for it
   (Preferences → Account Security → New API Key). I'll give you the bot user's
   **email**, the **API key**, the **Odoo.sh URL**, and the **production database
   name**. The API key replaces the password.

4. **DNS (my manual step — give me the exact value).** Tell me to add an **A
   record** `delivery` → my VPS IP in Hostinger hPanel → DNS Zone for
   `mumtaz.digital`. Wait until `dig +short delivery.mumtaz.digital` returns the
   VPS IP before continuing.

5. **Install on the VPS.** Clone the repo there (or use the local copy if you're
   on the VPS), `cd` in, and run `sudo bash deploy/setup.sh`. It will prompt for:
   Anthropic API key, model id (`claude-sonnet-4-6`), Odoo URL, Odoo user (the bot
   email), Odoo password (the **API key**), a console login user+password (ask me
   what I want), and the domain (`delivery.mumtaz.digital`). Collect these from me
   and supply them to the prompts. The secrets land only in
   `delivery_api/.env` (chmod 600) — do not echo them into any committed file or
   into a log.

6. **HTTPS.** Once DNS resolves:
   `sudo apt-get install -y certbot python3-certbot-nginx && sudo certbot --nginx -d delivery.mumtaz.digital`.

7. **Verify Odoo connectivity.** With the production **database name**, hit the
   API: `curl -u USER:PASS https://delivery.mumtaz.digital/api/odoo/<DB_NAME>/modules`
   and confirm it returns the installed-module list. If it errors, diagnose:
   Odoo.sh external API reachable over https? bot user has the right access?
   correct db name? key valid?

8. **End-to-end check.** Confirm `systemctl status delivery-api` is active and
   `/api/health` returns ok. Then open the console, create a test engagement with
   the Odoo DB set, run **Presales**, and confirm a `crm.lead` appears in Odoo.
   Report what you verified.

## Constraints

- **Secrets:** only in `delivery_api/.env` on the server. If you need one, ask me
  and use it directly — never commit it, never write it into a log or a file
  that gets pushed.
- **Don't rebuild the code.** Deploy the existing, tested package. Modify a file
  only if a deploy step truly requires it, and tell me exactly what you changed
  and why.
- Keep the basic-auth login — this is an internal operator tool.
- For anything you can't do yourself (DNS, the Odoo bot user, paying-attention
  manual clicks), give me precise instructions and wait for me to confirm.

## What I'll give you when you ask

Anthropic API key · Odoo.sh URL + production database name · bot user email + its
API key · console login user/password · VPS SSH details (or confirmation you're on
the VPS) · GitHub repo name + `gh` auth.
