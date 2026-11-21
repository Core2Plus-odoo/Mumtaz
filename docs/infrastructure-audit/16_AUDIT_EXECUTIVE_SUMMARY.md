# 16 — Audit Executive Summary

**Date:** 2026-11-21 · **Mode:** read-only · **Changes made to any system:** none

## What was examined

The whole GitHub repository `Core2Plus-odoo/Mumtaz` — every branch, the full history, CI results and open pull requests — plus a line-level security review of all application code on `main`.

**What was not examined:** the server itself. This audit had no SSH access, could not reach the production websites, and connected to no database. Statements about the live server come from command output the owner pasted into repository documents between 5 October and 20 November 2026. They are credible but unconfirmed, and are labelled "Reported" throughout. A one-page read-only script (`13_REMEDIATION_BACKLOG.md`) will confirm or correct them in about half an hour.

## What exists

One repository and one Hostinger VPS carry **fourteen projects belonging to at least four different data owners**:

- the group's own CRM and ERP (41 users, 41,000 leads);
- **a client's accounting system** (two legal entities' books);
- **Faizy**, a separate consumer product holding customers' identity documents;
- demo/staging tenants (Jewel, Pharma), an AI delivery console, three half-built platform services, two WordPress sites and a scraper.

Seven Odoo instances, one FastAPI service and several leftovers run side by side on that one host. Most share a single database login and a single operating-system user.

## The five things that matter most

1. **The repository is public.** Anyone can read the server's address, which port each system listens on, the database names, a client's name and customer list, staff names, and a written statement that one internet-reachable system still has a weak administrator password.
2. **Systems are reported to be reachable directly from the internet, bypassing the secure front door.** The client's accounting system is used over an unencrypted connection on a raw port. Passwords and financial data travel in clear text.
3. **There is no working backup.** The "nightly backup" job has run 920 times and failed every time, before doing anything, because of a syntax error. No production database, attachment store or application database has a verified, off-server copy. A disk failure today would be unrecoverable.
4. **Nobody can say exactly what code production is running.** The servers track an unmerged feature branch rather than `main`; some modules exist only on the server; 25 business rules live only inside the CRM database. The documented deployment process describes a setup that was never built.
5. **Tenant separation is weaker than it looks.** A shared secret lets one customer's administrator sign in to another customer's system; two production processes open every database on the server; one database is served by two programs at once; any logged-in user can read every company's financial summary. In Faizy, any customer can read every other family's identity documents.

Beyond these, the code review produced 99 itemised findings (3 Critical, 25 High). The well-built parts are worth naming too: the jewellery modules are tested and carefully scoped, Faizy's server layout is properly isolated, the Pharma and Jewel deployment kits are exactly the pattern the rest should follow, and no API key or password was found in 1,089 commits of history.

## Risk count

| Severity | Count | Examples |
|---|---|---|
| Critical | 5 | Exposed ports and weak credential · no backups · public repository · cross-tenant login · unauthenticated finance API |
| High | 15 | Unknown production code · shared database login · wrong database wiring · client system without staging · broken CI · possible domain lapse · identity documents exposed |
| Medium | 19 | No monitoring · secrets handling · false e-invoice status · stray databases with real data |
| Low | 7 | Branch sprawl · stale documentation |

## What is unknown

Whether each "Reported" item is still true today; which ports are actually open; which database each website really opens; whether Hostinger snapshots exist; certificate and domain expiry dates; whether the half-built services are running; which modules are installed where; who holds access to the server, the registrar and GitHub.

## Recommended priorities

| Order | Step | Disruption |
|---|---|---|
| 1 | Run the read-only verification script; name an owner for each system | None |
| 2 | Make the repository private; change the weak administrator password | None |
| 3 | Take the first real backups, copy them off the server, restore one to prove it | Brief extra load |
| 4 | Put the client system behind HTTPS and close every direct port | One short restart, announced to the client |
| 5 | Fix the database wiring so each program touches only its own database | Two short restarts |
| 6 | Then: automated backups and monitoring, reconcile the code, separate the projects, fix the application flaws, modernise deployment | Planned windows |

Total effort is roughly **28–38 engineer-days** across eight phases (`14_IMPLEMENTATION_ROADMAP.md`). Steps 1–5 are about four days and remove the risks that could end a client relationship or lose data outright.

## What is being asked for now

Approval of the **first batch only** (given by the owner on 2026-11-21; see `15`) — steps 1 and 2 above, plus closing one pull request. It restarts nothing and changes nothing a user can see. Details and the sign-off table are in `15_DECISIONS_AND_APPROVALS.md` §4.

Three decisions are needed alongside it:

- **D-01** where this audit pack is kept — decided by the owner on 2026-11-21: committed to the repository while it is still public;
- **D-02** who owns each system;
- **D-03** how server evidence is gathered (recommended: the owner runs the script and pastes the output privately).

## Document index

| # | Document | Use it for |
|---|---|---|
| 01 | Environment Inventory | What exists, where, with what evidence |
| 02 | Project ↔ Website ↔ Database Mapping | Which site opens which database |
| 03 | Current Architecture | The picture, and where docs and reality diverge |
| 04 | Security Audit | Every security finding with location and fix |
| 05 | Database Audit | Databases, roles, read-only checks to run |
| 06 | Odoo Instances Audit | Instances, modules, crons, overrides |
| 07 | Repository Structure Audit | Duplicates, orphans, monorepo decision |
| 08 | Deployment and CI/CD Audit | What deploys how; target release flow |
| 09 | Backup and Recovery Audit | Coverage, gaps, target standard |
| 10 | Risk Register | Ranked findings |
| 11 | Target Architecture | Where this should end up |
| 12 | Reorganization Plan | Path-by-path mapping and change register |
| 13 | Remediation Backlog | Every action; the verification script |
| 14 | Implementation Roadmap | Phases, gates, effort |
| 15 | Decisions and Approvals | Audit trail; first batch for sign-off |
| 16 | This summary | — |
