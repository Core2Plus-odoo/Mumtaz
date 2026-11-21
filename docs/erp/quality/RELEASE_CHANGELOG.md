# Release changelog (platform and C2P modules)

Jawhar's record is docs/mumtaz-jewel/PLAN_V3_RECONCILIATION.md; the C2P console's is c2p-delivery-system/docs/05-build-log.md.

| Date | Release | Modules | Evidence |
| --- | --- | --- | --- |
| 2026-11-20 | Wave 0 audit and design documents | docs/erp | this folder |
| 2026-11-21 | Backlog item 1 (PR "Fresh-database install CI for every platform module"): `scripts/platform_ci.sh` and `.github/workflows/platform-odoo-install.yml`. Four modules could not install on a clean Odoo 19 database and were fixed: `c2p_project_tracker` (undeclared `sale` dependency; `expand`/`string` on search `<group>`; report `groups_id`), `mumtaz_org_config` (same search attributes), `mumtaz_organization` (menu `groups_id`; missing `action_view_signups`), `mumtaz_customer_portal` (five portal xpaths and one template id gone in 19). The tracker's 57 tests, never run on 19 by automation, failed in 20 places on the Datetime deadline; fixed through `_c2p_deadline_date()`, sync on task creation and explicit health recomputation. | c2p_project_tracker, mumtaz_org_config, mumtaz_organization, mumtaz_customer_portal, scripts, workflows | platform_ci: 39/39 installed, 57 tests 0 failed; jewel_ci: 242 tests 0 failed |
