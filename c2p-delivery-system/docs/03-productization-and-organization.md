# C2P Agency OS — Productization & Organization Plan

> How to turn the internal agency system into a **standalone product C2P can
> sell**, and how to **organize everything** (Odoo.sh projects, the IP built on
> Claude, the repos) into one canonical home. Companion to the Master Build Brief.

---

## 1. The shift: from internal tool to product

C2P Consultants becomes **customer #0**. You build the agency OS to run your own
firm, prove it on your own pipeline, then license the *same codebase* to other
Odoo partners. One build serves both — your delivery engine and your product are
the same thing. This is the C2P Ventures line: **"the operating system for AI-run
Odoo delivery agencies."**

## 2. What you're selling

- **Product:** an AI-operated agency OS — lead-to-delivery, with specialist Odoo
  agents, an approval layer, and compounding client knowledge.
- **Who buys it:** Odoo partners and boutique ERP/implementation consultancies,
  and digital agencies doing Odoo work — concentrated first where you already have
  reach (GCC, Pakistan, emerging markets), then wider.
- **The promise:** run the throughput of a much larger agency without growing
  headcount, at consistent quality, with the owner approving only the decisions
  that carry money, reputation, or production code.
- **Why it's defensible:** the system prompts (your Odoo + delivery IP), the
  approval discipline, and the per-client knowledge that compounds — not easily
  copied, and it gets stronger with use.

## 3. From internal to multi-tenant product

The architecture changes are contained, because the backbone was built for it.

| Concern | Internal (now) | Product (multi-tenant) |
|---|---|---|
| Tenancy | one agency (C2P) | each customer agency = a tenant |
| Data isolation | single store | **per-tenant isolation** for client knowledge (sensitive); shared control plane |
| Brand | C2P brand | **white-label** — tenant sets logo, colours, domain; proposals/console carry *their* brand |
| Odoo | your Odoo.sh | **bring-your-own** — each tenant connects their own Odoo(s) |
| AI keys | your key | tenant's own key, or metered usage you resell |
| Comms | your channels | tenant's own email/WhatsApp |
| Config | hard-set | per-tenant: ICP, autonomy policy, approval thresholds, templates, pricing rules |

**Recommended tenancy model:** a shared control plane (auth, billing, the agent
engine and orchestration) over **per-tenant data stores** for accounts, client
knowledge, and engagements — consistent with your Mumtaz one-DB-per-tenant stance
and appropriate given you're holding *other agencies' client data*. The agent
layer is shared code; the data is isolated.

**White-label is non-optional for selling.** Every client-facing artifact (the
proposal PDF, the portal, outbound comms) must render in the tenant's brand, not
C2P's. Build the brand as tenant config from the start.

## 4. Packaging (editions)

Sell in tiers that map to the build phases, so each is shippable on its own:

| Edition | Includes |
|---|---|
| **Delivery** | Functional + Developer + Project agents, console, Odoo write-back |
| **Growth** | + Prospector, Researcher, Qualifier, branded Proposals, Approval layer |
| **Agency** | + Communications, Client Knowledge, Agency Cockpit, white-label, multi-user |

Add-ons: voice briefings, extra Odoo connections, higher usage tiers.

## 5. Pricing model (choose the lever, not the number)

Pick what you meter; set figures from your own unit economics. Options, strongest
first for this product:

- **Per active engagement / project** — scales with the value the tenant gets;
  aligns price with their revenue.
- **Per-tenant subscription + usage** — flat platform fee per edition, plus
  metered agent runs or AI usage above an allowance.
- **Per seat** — simplest to sell, weakest alignment to value.
- **% of pipeline or delivered value** — highest alignment, hardest to administer.

A platform-fee + per-engagement blend usually fits agencies best. (Keep your own
numbers out of the spec until you've modelled them.)

## 6. Trust & security (you're holding other agencies' client data)

This is a sales gate, not an afterthought: per-tenant data isolation; each tenant's
secrets (Odoo creds, AI keys, comms tokens) encrypted and scoped to that tenant;
a full audit trail of every agent action and approval; clear data-residency and
deletion policy; and the approval layer as the visible control that says *nothing
goes to a client without a human*. Lead with this for enterprise/partner buyers.

---

## 7. Organize everything — the canonical home

Right now value is scattered: Odoo.sh projects, repos, and a lot of **IP living
inside Claude conversations** (system prompts, briefs, decisions). Consolidate into
one monorepo as the single source of truth.

```
c2p-agency-os/
├── README.md                 # what this is + how it's organized
├── docs/                     # the thinking, version-controlled
│   ├── 00-vision.md
│   ├── 01-architecture.md
│   ├── 02-agents.md
│   ├── 03-productization.md  # this plan
│   ├── 04-organization.md
│   └── prompts/              # build/deploy prompts (e.g. the Claude Code brief)
├── api/                      # the FastAPI backbone — the product engine
│   ├── prompts.py            # the agent system prompts = the core IP
│   ├── main.py, store.py, sync.py, odoo.py, models.py, requirements.txt
├── console/                  # operator UI(s)
├── deploy/                   # installer, service, nginx, multi-tenant notes
├── odoo-addons/              # Odoo-side modules per Odoo.sh project (submodules)
└── .gitignore
```

### 7a. Capture the Claude IP into version control

The most valuable, least-organized asset is the IP built up in chat: the agent
system prompts, the build briefs, the design decisions. Move it where it lives
durably:
- Agent **system prompts** → `api/prompts.py` (already there) — this *is* the
  product's brain; treat it as core IP, reviewed and versioned.
- **Briefs, specs, decisions** → `docs/` — the build brief, this plan, deploy
  prompt, and a running decisions log.
- Going forward, anything decided in a Claude session that matters gets written
  into `docs/`, so the repo, not the chat history, is the source of truth.

### 7b. Odoo.sh projects & GitHub org

- Keep a **connections registry** (`docs/04-organization.md` + per-tenant config):
  each Odoo.sh project = an environment a tenant connects to, with its addons repo.
- **GitHub org `Core2Plus-odoo`**, clear repos: `agency-os` (the product),
  `mumtaz` (existing), and one addons repo per Odoo.sh project. Consistent naming.
- **Environments:** Odoo.sh already gives you prod/staging/dev branches per
  project; mirror that with the product's own dev/staging/prod. Custom modules the
  Developer agent generates flow into the right addons repo → Odoo.sh build.

### 7c. Consolidation checklist

1. Create `Core2Plus-odoo/agency-os` and drop in the organized starter repo (below).
2. Move every loose Claude artifact (prompts, briefs, HTML tools) into `docs/`,
   `api/`, `console/` — archive duplicates.
3. List your Odoo.sh projects and their addons repos in `docs/04-organization.md`;
   tag which is C2P's own (Tenant #0) vs client/Mumtaz.
4. Make the repo the source of truth; from now on, decisions land in `docs/`.

---

## 8. Phasing to a sellable product

- **P0 — Organize (now).** Stand up the monorepo; capture the IP; one source of truth.
- **P1 — Internal-ready.** Run C2P Consultants entirely on it (customer #0, dogfood).
- **P2 — Multi-tenant core.** Tenancy, per-tenant isolation, tenant config, auth.
- **P3 — White-label + billing.** Tenant branding, subscription/usage metering, onboarding.
- **P4 — First external pilot.** One friendly Odoo-partner agency; harden from real use.
- **P5 — GA.** Editions, self-serve, security posture, the sales motion.

Sell only what you've dogfooded. C2P running on it *is* the proof.

## 9. Definition of done (product)

A new agency signs up, connects their own Odoo and channels, sets their brand and
autonomy policy, and runs their full lead-to-delivery lifecycle on the platform —
their client data isolated, their team approving the gated decisions — while C2P
Consultants runs its own agency on the same system. One codebase, two outcomes:
your firm's leverage, and a product you sell.

---

### Next
Build prompts for each phase live in `docs/prompts/`. Start with **P0/P1**: stand
up the organized repo and run C2P on it before opening multi-tenancy.
