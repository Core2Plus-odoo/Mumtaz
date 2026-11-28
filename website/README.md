# website

| Path | What it is | May it move? |
| --- | --- | --- |
| `jewel/` | The Jawhar public site (seven static pages, real product screenshots, a working demo-request form). Deployed by `deploy/jewel-staging/`, which copies it to the server's landing folder | **Not without a server step**: the deploy kit and the link check in CI use this path |

The one-page landing that used to sit beside it (`index.html`, `assets/`)
moved to `sites/delivery.mumtaz.digital/landing/` on 22 Nov 2026: it markets
the delivery console, and the server check showed nothing serves it.

The Mumtaz marketing site is not here: see `sites/mumtaz.digital/README.md`
and `docs/platform/MUMTAZ_WEBSITE_IMPLEMENTATION.md`.
