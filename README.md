# Mumtaz Digital

An AI-first business platform for the GCC and Pakistan, built on **Odoo 19
Community** plus proprietary `mumtaz_*` modules: a multi-tenant SaaS shell,
industry editions (Jawhar for jewellery is the first), an AI layer (ZAKI) and
white-label deployment for partners.

**Read [`REPO_MAP.md`](REPO_MAP.md) first**, and [`sites/`](sites/) for a website-by-website view (one folder per site: what it is, where its code lives, its database, how it deploys). This repository holds more than
one product and several generations of the same component. The map says what
each folder is, which copy is which, and what is still undecided.

## What is here

| Area | Where | State |
| --- | --- | --- |
| Odoo modules (63, plus 6 Faizy modules under `faizy/`) | `addons/` | Listed with layer, dependencies and test count in [`registry.yaml`](registry.yaml) |
| Jawhar web app | `apps/jawhar-web` (React + TypeScript + Vite) | Talks to Odoo through `mumtaz_jewellery_api` |
| Customer portal, marketplace, ZAKI front ends | `sites/<domain>/`, `platform/` | Several variants; see the duplicates table in `REPO_MAP.md` |
| Marketing sites | `sites/mumtaz.digital/site`, `website/`, `platform/marketing` | Three variants; see `REPO_MAP.md` |
| C2P Agency OS | `c2p-delivery-system/` | Separate product; documented in `CLAUDE.md` |
| Other ventures | `faizy/`, `wordpress-sites/` | Not part of Mumtaz; candidates to move out |

## Module layers

Every module is classified in `registry/classification.json`:

1. **foundation** — shared base (`mumtaz_core`, branding, theme)
2. **platform** — the SaaS shell: tenants, control plane, billing, SSO, routing, portals
3. **product** — generic business and AI modules: e-invoicing, reports, ZAKI, marketplace
4. **edition** — industry packs: `mumtaz_jewellery*` (Jawhar)
5. **internal** — C2P's own modules and business-development tooling
6. **venture** — unrelated ventures kept here for now

A module may depend only on its own layer or a lower one. CI enforces this:

```bash
python3 scripts/module_registry.py --check   # what CI runs
python3 scripts/module_registry.py --write   # after adding or changing a module
```

A new module must be added to `registry/classification.json` or CI fails.

## Running and testing

```bash
docker compose up                 # Odoo 19 + Postgres, addons mounted
bash scripts/jewel_ci.sh          # Jawhar Odoo test suite on a fresh database
bash scripts/platform_ci.sh       # install + upgrade every platform module
bash scripts/tenant_journey_ci.sh # registration -> entitlement -> real staging tenant database -> sign-in
```

The scripts document their own prerequisites. Workflows are in
`.github/workflows/`.

## Rules for changing anything

- `docs/erp/DEVELOPMENT_STANDARDS.md` governs every addon change.
- `docs/mumtaz-jewel/CLAUDE.md` governs Jawhar and is stricter.
- Production deploys from `main`. Work on a branch and open a pull request.
- No secrets in git. Use the `.env.example` files.

## Documentation

- `docs/README.md` — index of every documentation set
- `sites/README.md` — every website with its code, database, status and open points
- `docs/platform/` — platform consolidation: architecture, product catalogue, control plane, AI, website, roadmap, handoff (start at its README)
- `docs/infrastructure-audit/` — read-only infrastructure and security audit (21 Nov 2026)
- `docs/erp/` — audit, capability matrix, roadmap, decision register, standards
- `docs/mumtaz-jewel/` — Jawhar architecture, slices, test reports
- `docs/operations/ARCHITECTURE.md`, `DEPLOYMENT.md`, `MONITORING.md`, `VPS_SETUP.md` — platform operations
- `docs/archive/README-legacy-2026-11.md` — the previous README, kept for reference; parts of it are out of date
