# Pharma staging — `pharma.mumtaz.digital`

Generic Odoo 19 Community tenant, database `mumtaz_pharma`, selected by the
existing `dbfilter = ^mumtaz_%d$`. **Staging only.** Fictional DEMO data
(`pharma_demo_data`, never for production). Branch: `pharma-erp-v0.1`.

| File | What it does |
| --- | --- |
| `discover.sh` | Read-only look at the VPS: Odoo runtime, `dbfilter`, addons path, databases, nginx, certs, DNS. Masks passwords. Run first. |
| `stage.sh` | `backup`, `install`, `test`, `serve-check`, `smoke`. Touches only `mumtaz_pharma` and the throwaway `mumtaz_pharma_test`. Never edits nginx/DNS/live `odoo.conf`, never restarts anything. |
| `nginx/pharma.mumtaz.digital.conf` | Server block mirroring `erp.mumtaz.digital` (with `/websocket`); certbot adds TLS. |

Order (the gates in bold need a named approval first):

```bash
git clone <repo> /opt/mumtaz-pharma-staging && cd /opt/mumtaz-pharma-staging && git checkout pharma-erp-v0.1
bash deploy/pharma-staging/discover.sh
bash deploy/pharma-staging/stage.sh backup
bash deploy/pharma-staging/stage.sh install      # -i <list> --without-demo, then sets the admin password
bash deploy/pharma-staging/stage.sh test         # expect "0 failed, 0 error(s) of 34 tests"
bash deploy/pharma-staging/stage.sh serve-check  # tells you whether the live service can see pharma_*
```
**DNS** A record `pharma -> 187.77.128.199` (Hostinger hPanel, like `delivery`/`jewel`) ·
**nginx** block + `certbot --nginx -d pharma.mumtaz.digital` · **addons visibility** for the
live service (symlink, or `addons_path` + restart) · then `stage.sh smoke`.

Full record, commands and rollback: `docs/pharma/DEPLOY_LOG.md`.
