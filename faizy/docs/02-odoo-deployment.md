# Faizy — Odoo Community Deployment

Standing up a **separate Odoo Community instance** for Faizy on its own domain.

Separate from Mumtaz in every layer that matters: its own database, its own
system user, its own service, its own port, its own domain and certificate.
Nothing here touches the existing Mumtaz or C2P delivery deployment.

> Placeholders used throughout: `faizy.example` for the domain (replace with the
> real one), `8079` for the HTTP port and `8078` for longpolling (chosen to avoid
> Odoo's default 8069/8072, which the existing instance already uses).

---

## 0. Before you start

| Need | Why |
|---|---|
| A VPS with 2 GB RAM free | Odoo plus a Postgres database of its own |
| The dedicated domain, DNS A record pointing at the server | Certificates and the website |
| PostgreSQL 14+ | Already installed on the current box |
| Python 3.10+ | Odoo 19 requirement |

**Do not install this alongside the existing instance on the same ports or the
same database.** Two Odoo instances sharing a database is a corruption story, not
a deployment.

---

## 1. Database and system user

Faizy gets its own Postgres role and database, so a mistake in one product's
database cannot reach the other.

```bash
sudo -u postgres createuser --createdb faizy
sudo -u postgres psql -c "ALTER ROLE faizy WITH PASSWORD 'CHANGE-ME';"
sudo -u postgres createdb --owner=faizy faizy_prod

sudo useradd -m -d /opt/faizy -U -r -s /bin/bash faizy
```

## 2. Odoo and the addons

```bash
sudo -u faizy git clone --depth 1 --branch 19.0 \
  https://github.com/odoo/odoo.git /opt/faizy/odoo

sudo -u faizy python3 -m venv /opt/faizy/venv
sudo -u faizy /opt/faizy/venv/bin/pip install --upgrade pip wheel
sudo -u faizy /opt/faizy/venv/bin/pip install -r /opt/faizy/odoo/requirements.txt

# Faizy's own modules
sudo -u faizy git clone https://github.com/Core2Plus-odoo/Mumtaz.git /opt/faizy/src
```

The addons path then includes `/opt/faizy/src/faizy/odoo/addons`.

> When Faizy moves to its own repository (recommended — `docs/00-decisions.md`
> §8.1), only that clone URL changes.

## 3. Configuration

`/opt/faizy/odoo.conf` — **never commit a filled-in copy of this**:

```ini
[options]
admin_passwd = CHANGE-ME-LONG-RANDOM
db_host = localhost
db_port = 5432
db_user = faizy
db_password = CHANGE-ME
; Pin to one database so the login page cannot enumerate the others on this box.
db_name = faizy_prod
dbfilter = ^faizy_prod$
list_db = False

addons_path = /opt/faizy/odoo/addons,/opt/faizy/src/faizy/odoo/addons
data_dir = /opt/faizy/data

http_port = 8079
longpolling_port = 8078
; Bind to loopback only — nginx is the sole public entrance.
http_interface = 127.0.0.1

proxy_mode = True
workers = 3
limit_time_cpu = 120
limit_time_real = 240
logfile = /var/log/faizy/odoo.log
log_level = info
```

```bash
sudo mkdir -p /var/log/faizy /opt/faizy/data
sudo chown -R faizy:faizy /var/log/faizy /opt/faizy/data
sudo chmod 640 /opt/faizy/odoo.conf && sudo chown faizy:faizy /opt/faizy/odoo.conf
```

`list_db = False` and the `dbfilter` matter more than they look: without them the
database manager is reachable from the internet and will happily offer to
duplicate or drop your production database.

## 4. Service

`/etc/systemd/system/faizy-odoo.service`:

```ini
[Unit]
Description=Faizy Odoo
After=network.target postgresql.service

[Service]
Type=simple
User=faizy
ExecStart=/opt/faizy/venv/bin/python3 /opt/faizy/odoo/odoo-bin -c /opt/faizy/odoo.conf
Restart=always
RestartSec=5
KillMode=mixed

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now faizy-odoo
sudo systemctl status faizy-odoo
```

## 5. Install the modules

```bash
sudo systemctl stop faizy-odoo
sudo -u faizy /opt/faizy/venv/bin/python3 /opt/faizy/odoo/odoo-bin \
  -c /opt/faizy/odoo.conf -d faizy_prod -i faizy_core,faizy_website --stop-after-init
sudo systemctl start faizy-odoo
```

Upgrading after a code change is the same command with `-u` instead of `-i`.

## 6. The dedicated domain

DNS first: an **A record** for the domain pointing at the server's IP. Wait for
`dig +short faizy.example` to return it before requesting a certificate — Let's
Encrypt validates over HTTP and fails if DNS has not propagated.

`/etc/nginx/sites-available/faizy`:

```nginx
upstream faizy_odoo      { server 127.0.0.1:8079; }
upstream faizy_longpoll  { server 127.0.0.1:8078; }

server {
    listen 80;
    server_name faizy.example www.faizy.example;

    access_log /var/log/nginx/faizy.access.log;
    error_log  /var/log/nginx/faizy.error.log;

    client_max_body_size 25M;   # CNIC scans and proof-of-delivery photos

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 720s;

    # Long-polling must go to its own port or realtime updates stall.
    location /longpolling { proxy_pass http://faizy_longpoll; }
    location /websocket   { proxy_pass http://faizy_longpoll; }

    location / {
        proxy_pass http://faizy_odoo;
        proxy_redirect off;
    }

    # Odoo fingerprints static assets, so they can be cached hard.
    location ~* /web/static/ {
        proxy_cache_valid 200 90m;
        proxy_pass http://faizy_odoo;
        expires 864000;
    }

    gzip on;
    gzip_types text/css text/plain application/javascript application/json image/svg+xml;
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/faizy /etc/nginx/sites-enabled/faizy
sudo nginx -t && sudo systemctl reload nginx

sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d faizy.example -d www.faizy.example
```

Then tell Odoo its own address, or generated links and emails will point at
`localhost`:

**Settings → Website → Domain** = `https://faizy.example`
**Settings → General → Technical → System Parameters** → `web.base.url` =
`https://faizy.example`, and add `web.base.url.freeze` = `True` so the next admin
login from another host does not silently overwrite it.

## 7. After install

1. **Company** — set to *C2P Consultants FZC LLC*, currency **AED**, and the
   correct address for invoices.
2. **Revenue policy** — Settings → Faizy: platform fee (5%), vendor commission
   (10%), free activities on signup (3). These are editable here precisely so
   changing them is never a deployment.
3. **Plan products** — each plan needs a subscription product and an overage
   product before the recurring cron can invoice. It refuses rather than
   guessing, and says so on the subscription's chatter.
4. **⚠️ Confirm the placeholder numbers** — `activities_included` per tier and
   the overage price are guesses (the brief never states them). Settings → Faizy
   → Configuration → Plans.
5. **Users and groups** — Agent / Operations / Manager. Only Operations and above
   can see medical notes.
6. **Scheduled actions** — confirm both are active: recurring invoicing (daily)
   and the WhatsApp queue (every 15 min).
7. **WhatsApp** — messages queue but do not send until a provider is configured;
   see `docs/00-decisions.md` §2.
8. **Put a CAPTCHA or rate limit in front of `/join`** before announcing it. It
   accepts anonymous submissions and the honeypot only stops naive bots.

## 8. Backups

```bash
# Database
sudo -u postgres pg_dump -Fc faizy_prod > /var/backups/faizy_$(date +%F).dump
# Filestore — attachments and photos live here, NOT in the database
tar czf /var/backups/faizy_filestore_$(date +%F).tar.gz /opt/faizy/data/filestore
```

A database dump without the filestore restores to an instance with every
attachment broken. Back up both or neither.

## 9. Health checks

```bash
systemctl status faizy-odoo
journalctl -u faizy-odoo -f
curl -sI https://faizy.example | head -1
curl -s https://faizy.example/pricing | grep -c "faizy-plan-card"   # expect 3
```

---

## Keeping the two instances apart

| | Mumtaz / C2P | Faizy |
|---|---|---|
| Database | `Mumtaz_ERP` | `faizy_prod` |
| System user | existing | `faizy` |
| HTTP port | 8069 | 8079 |
| Longpolling | 8072 | 8078 |
| Service | existing | `faizy-odoo` |
| Domain | `*.mumtaz.digital` | the dedicated domain |
| Addons | `/opt/mumtaz/addons` | `/opt/faizy/src/faizy/odoo/addons` |

If a command in this document names a Mumtaz path or database, stop — it is the
wrong document.
