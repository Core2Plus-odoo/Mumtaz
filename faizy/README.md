# Faizy

WhatsApp-first family care for Pakistani expats in the GCC. Customers subscribe;
a network of vetted on-ground workers in Pakistan ("Faizies") run errands and
provide care for their family back home.

Operated by **C2P Consultants FZC LLC**.

> **Read `docs/00-decisions.md` first.** It answers every open question from the
> build brief and flags three decisions that need sign-off before the relevant
> code can be written.

---

## Status

| Layer | State |
|---|---|
| Monorepo, brand system, database, data layer, WhatsApp queue | **Built** |
| Database schema | **Verified** — applies cleanly, 36/36 business-rule checks pass |
| Customer / admin / worker apps | **Scaffolded** — feature work blocked, see below |
| Payments | **Not started** — awaiting gateway decision |

### Blocked on missing files

The prototypes named in the brief (`faizy-final.html`, the Faizy `admin.html`,
`vendor-onboarding.html`, `schema.sql`, `supabase-integration.js`,
`DEPLOYMENT_GUIDE.md`) **are not in this repository** — checked across every
branch and the full commit history. The customer app, admin panel and worker
onboarding wizard have deliberately not been rebuilt from guesswork, because the
brief states those files encode decisions that should not be re-litigated.

Everything that does not depend on them is built and tested.

---

## Layout

```
faizy/
├── apps/
│   ├── customer/          Customer PWA (Next.js, port 3000)
│   ├── admin/             Internal ops console (port 3001)
│   └── worker/            Faizy ground-staff PWA (port 3002)
├── packages/
│   ├── brand/             Design tokens + Tailwind preset  ← single source of truth
│   ├── ui/                Shared components (logo, buttons, FMB chip, status badges)
│   └── db/                Typed Supabase client, auth, orders, money
├── supabase/
│   ├── migrations/        8 migrations — schema, RLS, storage
│   ├── functions/         Edge Functions (WhatsApp queue drain)
│   ├── tests/             Shim + business-rule regression tests
│   └── seed.sql           Plans and demo Faizies
├── scripts/verify-db.sh   Verify the schema on any Postgres, no Docker needed
└── docs/
    ├── 00-decisions.md    ← START HERE
    └── 01-milestones.md   Plan and estimates
```

## Getting started

```bash
pnpm install

# Verify the database logic without any cloud dependency:
./scripts/verify-db.sh

# Run an app (needs a Supabase project — see docs/01-milestones.md M1):
pnpm --filter @faizy/customer dev
```

Copy `.env.example` and fill it in. Nothing secret is committed.

## Ground rules

**The database is authoritative for money and entitlements.** Platform fee (5%),
vendor commission (10%), activity counting and the paywall are computed by
Postgres triggers and `SECURITY DEFINER` functions. The columns behind them are
`REVOKE`d from client roles. Client-side helpers like `previewOrderTotals()` are
display conveniences — if they ever disagree with the database, the database is
right.

**The anon key is public.** It ships in every browser and installed PWA. RLS is
the only thing protecting one customer's family records, medical notes and CNIC
scans from another's. Every table is deny-by-default; see
`supabase/migrations/*_rls.sql`.

**The service-role key never reaches a browser.** `createFaizyAdminClient()`
throws if called client-side. Admin privileged reads go through server route
handlers.

**Brand tokens live in one place.** `packages/brand/src/tokens.ts`. The old
blue/gold + Cormorant Garamond identity is gone; nothing should reintroduce it.

## Verifying the database

`./scripts/verify-db.sh` applies a Supabase shim, all migrations, the seed, and a
36-check regression suite covering fee computation, the free-activity grant, the
paywall, overage billing, order lifecycle, notification queueing, rating averages
and constraint enforcement. It needs only PostgreSQL and psql — no Docker, no
network, no Supabase project. Run it before every migration PR.
