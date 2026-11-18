# Pharma staging — `pharma.mumtaz.digital`

Generic Odoo 19 Community tenant, database `mumtaz_pharma`. **Staging only.**
Fictional DEMO data (`pharma_demo_data`, never for production). Branch
`pharma-erp-v0.1`, cloned at `/opt/mumtaz-pharma-staging` (never `/opt/mumtaz`).

Shape, matching the other tenants on this VPS (one `odooN.service` +
`/etc/odooN.conf` + one nginx vhost each): its own unit **`odoo-pharma.service`**,
**`/etc/odoo-pharma.conf`** with `dbfilter = ^mumtaz_%d$`, ports
`127.0.0.1:8076` (http) / `8077` (websocket), the same local Postgres. The live
`/etc/odoo/odoo.conf` (dbfilter `^Mumtaz`, serving the production tenants) is
never edited and its service never restarted.

| File | What it does |
| --- | --- |
| `discover.sh` | Read-only look at the VPS. Masks passwords. |
| `stage.sh` | `backup`, `install`, `test`, `service` (gate), `smoke-local`, `smoke`, `service-remove`. Touches only `mumtaz_pharma` and the throwaway `mumtaz_pharma_test`. |
| `nginx/pharma.mumtaz.digital.conf` | Vhost like `erp.mumtaz.digital`, with `/websocket`; certbot adds TLS. |

```bash
bash deploy/pharma-staging/discover.sh
bash deploy/pharma-staging/stage.sh backup
bash deploy/pharma-staging/stage.sh install      # -i <list> --without-demo, then sets the admin password
bash deploy/pharma-staging/stage.sh test         # expect "0 failed, 0 error(s) of 34 tests"
bash deploy/pharma-staging/stage.sh service      # GATE: new unit on 8076/8077
bash deploy/pharma-staging/stage.sh smoke-local  # dbfilter + menus + demo mode, before DNS
# GATE: DNS A record pharma -> 187.77.128.199 (Hostinger hPanel)
# GATE: nginx vhost + certbot --nginx -d pharma.mumtaz.digital
bash deploy/pharma-staging/stage.sh smoke
```

Full record, commands and rollback: `docs/pharma/DEPLOY_LOG.md`.

## Accounting kit (third party, gated)

Odoo 19 Community has no financial reports, assets, budgets or bank-statement import. `docs/pharma/ACCOUNTING_KIT.md` records the
review of the Cybrosys kit, two findings (an unguarded Excel export route; a support form that can send data to the vendor) and the
`pharma_accounting_hardening` module that closes them. Steps, each separate, none touching nginx or DNS:

```bash
bash deploy/pharma-staging/stage.sh thirdparty        # fetch the pinned commit into /opt/thirdparty (source only)
bash deploy/pharma-staging/stage.sh deps              # gate: pip --target into /opt/thirdparty/pydeps
bash deploy/pharma-staging/stage.sh test-kit          # vendor tests, throwaway DB without our modules
bash deploy/pharma-staging/stage.sh test-combined     # our tests + kit + hardening, throwaway DB
bash deploy/pharma-staging/stage.sh install-accounting  # gate: dump, install, neutralize, restart odoo-pharma only
```
