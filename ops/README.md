# Operations files

nginx definitions, Odoo configuration samples and deploy scripts collected
from several generations of the platform. **None of these is confirmed to be
what the server runs.** Compare with the live configuration (`nginx -T`,
`/etc/odoo*.conf`) before using any of them.

| Folder | Content | State |
| --- | --- | --- |
| `deployment/` | Deploy scripts for the static sites and addons; four nginx definitions; two Odoo config samples; a module-detection guide | Mixed. The static-site scripts point at the `sites/` folders. The nginx files overlap each other and the ones under `platform/ops/nginx/` |
| `platform-routing/` | Wildcard-subdomain nginx and Odoo settings for database-per-tenant routing (was `apps/platform`) | Reference for the tenant routing still to be built (`docs/platform/MUMTAZ_SAAS_CONTROL_PLANE.md` §6) |
| `addons-deploy/` | Script that copies addons to `/opt/custom_addons` (was `apps/addons`) | Unverified; the Odoo services are reported to read a git checkout instead |

Known overlap: five nginx definitions exist in this repository for the main
domain and for `app.`, four for `zaki.`. The server reports one of them as a
conflict (`conflicting server name "www.mumtaz.digital"`, seen 22 Nov 2026).
The plan is one file per hostname (audit change R-12), written from the live
configuration, not from these.
