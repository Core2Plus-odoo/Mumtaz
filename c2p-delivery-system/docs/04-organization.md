# Organization & connections registry

This repo is the single source of truth. IP that used to live in Claude chats now
lives here: agent prompts in `api/prompts.py`, briefs and decisions in `docs/`.

## Odoo.sh projects (fill in)
| Project | Purpose | Addons repo | Notes |
|---|---|---|---|
| _e.g. c2p-consultants_ | C2P's own Odoo (Tenant #0) | Core2Plus-odoo/c2p-consultants | dogfood |
| _e.g. mumtaz_ | Mumtaz platform | Core2Plus-odoo/Mumtaz | |
| _client…_ | client tenant | … | |

## GitHub (Core2Plus-odoo)
- `agency-os` — this product
- `mumtaz` — Mumtaz platform
- one addons repo per Odoo.sh project

## Environments
Odoo.sh prod/staging/dev per project; mirror dev/staging/prod for the product.

## Decisions log
Record significant decisions here so the repo, not chat history, is the source of truth.
