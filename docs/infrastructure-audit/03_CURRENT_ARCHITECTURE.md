# 03 — Current Architecture (as documented, not as verified)

Everything below the "VPS" line comes from owner-run output recorded in the repository (R-doc, 2026-10-05 → 2026-11-20) or from configuration (INF). No server was inspected in this audit.

## 1. One host, many owners

```mermaid
flowchart TB
  subgraph NET[Internet]
    U[Browsers / API clients]
  end

  subgraph DNS[DNS — Hostinger]
    D1[mumtaz.digital + 10 subdomains]
    D2[core2plus.com]
    D3[myfaizy.com]
  end

  U --> DNS
  DNS --> NGX

  subgraph VPS[Hostinger VPS 187.77.128.199 · Ubuntu 24.04 · single host]
    NGX[nginx :80/:443 · one vhost per site · certbot]

    subgraph GROUP[Core 2 Plus group — own systems]
      O4[odoo4 :8075]
      O1[odoo :8069 · dbfilter ^Mumtaz]
      O2[odoo2 :8070]
      API[delivery-api :8800 FastAPI]
    end

    subgraph CLIENT[Client system]
      O3[odoo3 :8071 on 0.0.0.0]
    end

    subgraph PRODUCT[Separate product]
      FZ[faizy-odoo]
    end

    subgraph STAGING[Staging / demo]
      PH[odoo-pharma :8076]
      JW[Docker: jewel odoo :8072/8073]
    end

    subgraph ORPHAN[Orphaned / unknown]
      ES[erp-server — crash-looping]
      ZS[zaki-server :8002 ?]
      ZN[zaki-ai node :3000 ?]
    end

    PG[(PostgreSQL · local · role 'odoo' shared)]
    PGF[(role 'faizy')]
    PGJ[(Postgres 16 container)]
    SQL[(SQLite delivery.db)]
    SQZ[(SQLite users.db)]
  end

  NGX -->|core2plus.com| O4
  NGX -->|erp. / admin.| O1
  NGX -. erp. /longpolling .-> JW
  NGX -->|delivery. /api| API
  NGX -->|myfaizy.com| FZ
  NGX -->|pharma.| PH
  NGX -->|jewel.| JW
  NGX -. app. zaki. marketplace. /api .-> ZS
  U ==>|plain HTTP, direct to port 8071| O3

  O4 --> PG
  O1 --> PG
  O2 --> PG
  O3 --> PG
  PH --> PG
  FZ --> PGF
  JW --> PGJ
  API --> SQL
  ZS --> SQZ
  ZS -. admin XML-RPC .-> O2
  API -. stored connection, XML-RPC .-> O4
```

Read the diagram for three things:

1. **Four Odoo instances and one staging tenant reach PostgreSQL through the same role.** Only Faizy and Jewel have their own.
2. **One client system is reached without nginx or TLS** (the thick arrow).
3. **Three boxes in the "orphaned" group have no maintained source** in the repository, yet templates still route traffic to them.

## 2. Request paths

| Site | Path |
|---|---|
| `core2plus.com` | DNS → nginx 443 → `odoo4` :8075 → PostgreSQL `Mumtaz_C2P` → filestore under the `odoo` data dir → SMTP out |
| `erp.mumtaz.digital` | DNS → nginx 443 → `odoo` :8069 (pinned to `Mumtaz_C2P`) **or** `odoo2` :8070 (`Mumtaz_ERP`) — unresolved; `/longpolling` → :8073 (Jewel container) |
| IG2 | browser → `http://IP:8071` → `odoo3` → PostgreSQL `Mumtaz_IG2` |
| `myfaizy.com` | DNS → nginx 443 → `faizy-odoo` → PostgreSQL `faizy_prod` (role `faizy`) → `/opt/faizy/data` filestore |
| `jewel.mumtaz.digital` | DNS → nginx 443 → static `/opt/mumtaz/jewel-landing`; Odoo prefixes → allow-list/basic auth → Docker `odoo:19` → Docker Postgres 16 `jewel_demo` → Docker volume filestore |
| `pharma.mumtaz.digital` | DNS → nginx 443 → `odoo-pharma` :8076 → PostgreSQL `mumtaz_pharma` |
| `delivery.mumtaz.digital` | DNS → nginx 443 → static console (symlink into the git checkout); `/api/` → uvicorn :8800 → SQLite files beside the code → LLM provider / GitHub / Odoo XML-RPC |
| `app.mumtaz.digital` | DNS → nginx → static `/var/www/app.mumtaz.digital`; `/api/` → :8002 `zaki-server` → SQLite `users.db` + Odoo admin XML-RPC |

## 3. Process and ownership model

| Layer | Current state |
|---|---|
| OS users | `odoo` runs five Odoo services; `faizy` runs one; the delivery API user is set by `setup.sh` (see `04_SECURITY_AUDIT.md`); Docker runs as root |
| Service manager | systemd units written by hand per tenant (`odoo`, `odoo2`, `odoo3`, `odoo4`, `odoo-pharma`, `faizy-odoo`, delivery API, `erp-server`); pm2 for Node services (INF) |
| Config | One `/etc/odooN.conf` per instance, same DB password copied between them (the C2P template literally says "COPY FROM /etc/odoo/odoo.conf") |
| Code on disk | `/opt/mumtaz` and `/opt/custom_addons/Mumtaz` (both on a feature branch), `/opt/mumtaz-pharma-staging`, `/opt/mumtaz-jewel-staging`, `/opt/faizy/src`, `/opt/thirdparty`, `/opt/zaki-server`, `/opt/erp-server` |
| Firewall | `ufw` with 22/80/443 from the setup script, **plus application ports opened by hand** (8071 recorded; others reported) |
| TLS | certbot per hostname; renewal assumed, verified only for `pharma.` |
| Logs | `/var/log/odoo/*.log`, pm2 logs, journald. No aggregation, no alerting |
| Monitoring | None found |
| Backups | Ad-hoc dumps for staging tenants on the same disk. None found for production |

## 4. What the repository says versus what runs

| Topic | Repository says | Server record says |
|---|---|---|
| Production deploy | "Deploys go to `main`; the VPS pulls main" (`CLAUDE.md`) | Both production checkouts are on `claude/resume-help-95ne9v` |
| Odoo runtime | Docker Compose, `odoo:19` + `postgres:15` (`docker-compose.production.yml`) | Native package `/usr/bin/odoo`, system PostgreSQL |
| Odoo version | "Odoo 16/17" (`README.md`) | 19.0-20260719 |
| Tenancy | "One isolated Odoo database per tenant", `dbfilter = ^mumtaz_%d$` | One systemd unit per tenant, mixed-case names, `dbfilter = ^Mumtaz` on the main unit |
| Platform API | `apps/zaki-server/` (README, ARCHITECTURE, five scripts) | Source deleted in July; service state unknown |
| Nightly backup | GitHub Action at 02:00 | Workflow file invalid; has never executed a step |
| Database name | `mumtaz`, `mumtaz_main`, `mumtaz_master`, `Mumtaz_ERP`, `mumtaz_erp` in different files | `Mumtaz_ERP` **and** `mumtaz_erp` both exist |

The practical consequence: **no document in the repository can be followed to rebuild this server.** Recovery after a disk loss would depend on memory.
