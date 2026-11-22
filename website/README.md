# website

Two unrelated things share this folder.

| Path | What it is | May it move? |
| --- | --- | --- |
| `jewel/` | The Jawhar public site (seven static pages, real product screenshots, a working demo-request form). Deployed by `deploy/jewel-staging/` | **Not without a server step**: the deploy kit and the link check in CI use this path |
| `index.html`, `assets/` | A one-page landing whose buttons all lead to `delivery.mumtaz.digital`. It markets the Agency OS, not Mumtaz | Kept in place: a CI job checks that these three files exist, and whether the server serves them is unknown. Intended home: `sites/delivery.mumtaz.digital/` |

The Mumtaz marketing site is not here: see `sites/mumtaz.digital/README.md`
and `docs/platform/MUMTAZ_WEBSITE_IMPLEMENTATION.md`.
