# Get the C2P Delivery System running — the short version

You need two things ready first:
- Your **Odoo login** (the URL, username, password) — only if you want the live
  Odoo connection now. The agents work without it; you can add it later.
- About **5 minutes**.

An AI key is **optional**: with `C2P_LLM_PROVIDER=none` (the free default) every
stage runs on the built-in Odoo/BA/PM/finance knowledge — no Anthropic account
needed. Set `anthropic` (paid) or an OpenAI-compatible endpoint like Ollama
(free) later for AI-written prose and module code. All knobs are documented in
`delivery_api/.env.example`.

That's it. You won't touch any code.

---

## Step 1 — Put the package on your server

**Option A — GitHub (recommended, makes updates easy).** Push this package to a
repo (e.g. `Core2Plus-odoo/c2p-delivery`), then in the hPanel **Terminal**:

```bash
git clone https://github.com/Core2Plus-odoo/c2p-delivery.git c2p-delivery-system
```

Later, to update: `cd c2p-delivery-system && git pull && sudo bash deploy/setup.sh`.
The included `.gitignore` keeps your secrets (`.env`, login file, database) out of
git automatically.

**Option B — upload the zip.** In Hostinger **hPanel → File Manager**, upload
`c2p-delivery-system.zip`, right-click → **Extract**. (Or in the Terminal:
`unzip c2p-delivery-system.zip`)

## Step 2 — Run one command

Open the hPanel **Terminal** and run:

```bash
cd c2p-delivery-system
sudo bash deploy/setup.sh
```

It will ask you a few simple questions — your Anthropic key, your Odoo login, a
**username and password you want for logging into the console**, and your domain
or server IP. Type the answers and press Enter. The script does everything else:
installs what's needed, starts the service, and sets up the web page with a login.

## Step 3 — Open it

When it finishes it prints a link. Open it, log in with the username and password
you chose, and the console is live — Presales → Proposal → Project → Functional →
Developer.

**To put it on delivery.mumtaz.digital:**
1. In Hostinger **hPanel → DNS Zone** for `mumtaz.digital`, add an **A record**:
   name `delivery`, value = your **VPS IP**. (This doesn't touch the main site.)
2. When `setup.sh` asks for the domain, type `delivery.mumtaz.digital`.
3. Once the record is live (a few minutes), add HTTPS:
   ```bash
   sudo apt-get install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d delivery.mumtaz.digital
   ```
   Then it's at `https://delivery.mumtaz.digital`.

---

## Good to know

- **Re-running is safe.** If something hiccups, just run `sudo bash deploy/setup.sh`
  again — it keeps your existing settings and won't duplicate anything.
- **Your secrets stay yours.** They're written to one file on your server
  (`delivery_api/.env`) that only you can read. Nobody else sees them.
- **Odoo optional at first.** No Odoo connection? The five agents still run; only
  the live "read the tenant's modules" and "write the lead/quotation/project back
  to Odoo" features need it. Add it anytime by editing `delivery_api/.env`.
- **Add HTTPS** once your domain points at the server — the script prints the two
  commands to run.

## If you get stuck

- See the service status:  `systemctl status delivery-api`
- Watch the logs live:     `journalctl -u delivery-api -f`
- The web server config is at `/etc/nginx/sites-available/c2p-delivery`.

Copy any error you see and send it over — it's almost always one line in `.env`.
