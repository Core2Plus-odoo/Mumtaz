# deploy

| Folder | What it is | May it move? |
| --- | --- | --- |
| `jewel-staging/` | Everything that runs the Jawhar staging site: Docker Compose (Odoo 19 + PostgreSQL), nginx definition, deploy, backup and verification scripts. Its own `README.md` is the runbook | **Not without a server step.** On the server the untracked `.env` (credentials) sits in this folder, and the scripts and the compose file reach the addons and the site through paths relative to it. Moving it in git would strand that file and break those paths on the next pull |

Other products deploy from their own folders:
`c2p-delivery-system/deploy/update.sh` (Agency OS), `faizy/` (Faizy),
`wordpress-sites/deploy/` (WordPress themes). Older, unverified scripts are
in `ops/deployment/` and `scripts/`.
