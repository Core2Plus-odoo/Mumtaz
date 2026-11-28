# Infrastructure audit (21 Nov 2026)

A read-only audit. Nothing on any server was inspected or changed: every
statement about the server comes from repository documents and earlier
owner-run output, and is marked as such.

| File | Content |
| --- | --- |
| `16_AUDIT_EXECUTIVE_SUMMARY.md` | **Start here** |
| `00_INFRASTRUCTURE_MAP.html` | One-page map of sites, services and databases |
| `01_ENVIRONMENT_INVENTORY.md`, `02_PROJECT_WEBSITE_DATABASE_MAPPING.md`, `03_CURRENT_ARCHITECTURE.md` | What exists: hosts, services, sites, databases and how they connect |
| `04_SECURITY_AUDIT.md` | Security findings (F-, ODOO-, APP-, C2P- series) |
| `05_DATABASE_AUDIT.md`, `06_ODOO_INSTANCES_AUDIT.md` | Databases and Odoo instances |
| `07_REPOSITORY_STRUCTURE_AUDIT.md`, `08_DEPLOYMENT_AND_CICD_AUDIT.md`, `09_BACKUP_AND_RECOVERY_AUDIT.md` | Repository, deployment and CI, backups |
| `10_RISK_REGISTER.md` | Risks ranked |
| `11_TARGET_ARCHITECTURE.md`, `12_REORGANIZATION_PLAN.md` | Where to go and the ordered changes (R-01 … R-17) |
| `13_REMEDIATION_BACKLOG.md`, `14_IMPLEMENTATION_ROADMAP.md` | Backlog and order of work, including the read-only verification script for the server (V-01 … V-12) |
| `15_DECISIONS_AND_APPROVALS.md` | Audit trail, open decisions, and the approval log for every server change |

Paths quoted inside these files are as they were on 21 Nov 2026. Folders
moved since then are listed in `sites/README.md` and `REPO_MAP.md`.
