# Claude Code handoff and staging plan for jewel.mumtaz.digital

Status: plan only. Nothing here has been run on any server. Items marked APPROVAL need a named yes first.

## 1. Setup (one time)
1. Clone the repo on the dev machine or a staging VPS user account (not the production deploy user) and check out `claude/mumtaz-jewellery-phase2`.
2. Keep `docs/mumtaz-jewel/CLAUDE.md` as the rules file. Start Claude Code from the repo root and say: "Follow docs/mumtaz-jewel/CLAUDE.md. Read IMPLEMENTATION_ROADMAP.md and continue Slice 0."
3. Give Claude Code only dev or staging credentials. No production `.env`, SSH keys to production, or the live CRM database.
4. APPROVAL: turn on branch protection for `main` (require a pull request) so a stray push cannot deploy.

## 2. Staging for jewel.mumtaz.digital (proposed)
| Item | Proposal |
| --- | --- |
| Compose | Reuse `docker-compose.staging.yml` as a separate compose project `mumtaz-jewel-staging`, own network |
| Database | Own Postgres volume and database; never the CRM database; DB-per-brand for demo tenants |
| Odoo | `FROM odoo:19`, addons mounted from the branch checkout; `-i mumtaz_jewellery,mumtaz_jewellery_vip,mumtaz_jewellery_owner` on a fresh database |
| Port | A free localhost port (not 8069 or 8070) behind nginx |
| nginx and TLS | New server block for `jewel.mumtaz.digital`; certificate via the existing method on the VPS; HTTP basic auth or IP allow-list while it is a demo |
| DNS | A record for `jewel` to the VPS IP; the owner or registrar holder makes this change |
| Data | Seed script with synthetic data only; clear "DEMO" label in the UI |
| Deploy | A script that pulls the staging branch only. It must refuse to run from `main` and must not call `deploy/update.sh` |
| Backups | Nightly dump of the staging database; one restore test before the demo |
| Monitoring | Health check and uptime alert for the staging URL |

## 3. APPROVAL gates (named human, in chat)
- Creating the DNS record and nginx block (production infrastructure).
- First start of the staging stack on the VPS.
- Any change to the existing `docker-compose.production.yml`, nginx config for other sites, or the shared Postgres.
- Opening the site beyond the allow-list, or putting real client data on it.

## 4. What Claude Code does best here
Slice 0 test suite and CI script; Slice 1 price-to-sale; the offline POS spike; the staging deploy script; the Arabic and RTL work; reviewing pull requests against the rules file.

## 5. What still needs a person
Compliance confirmer (finance manager) naming; ElevenLabs account and API key as an environment variable; WhatsApp provider; the DNS change; reviewing Arabic voice utterances with native-speaker jewellers.
