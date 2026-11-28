# apps

| Folder | What it is | May it move? |
| --- | --- | --- |
| `jawhar-web/` | The Jawhar web app (React, TypeScript, Vite). Talks to Odoo through `mumtaz_jewellery_api` | **Not without a server step.** The Jawhar deploy kit (`deploy/jewel-staging/`), its container mounts and the `jawhar-web.yml` workflow use this path |

The other folders that used to be here moved to `sites/<domain>/` and `ops/`
on 21 Nov 2026; the table is in `sites/README.md`. Jawhar's website-level
description is `sites/jewel.mumtaz.digital/README.md`.
