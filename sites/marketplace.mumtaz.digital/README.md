# marketplace.mumtaz.digital

B2B marketplace: public storefront and vendor portal. Two static pages that call a back-end API.

| | |
|---|---|
| **Status** | **Orphaned.** Depends on the same deleted `zaki-server` API as the customer portal |
| **Code in this folder** | [`storefront/`](storefront/) — `index.html` (public) and `vendor.html` (moved from `apps/marketplace/`) |
| **Related Odoo module** | [`addons/mumtaz_marketplace/`](../../addons/mumtaz_marketplace/) |
| **Database** | Through the deleted API; listings live in Odoo |
| **Served by** | nginx, web root `/var/www/marketplace.mumtaz.digital` |
| **Deploy** | `ops/deployment/deploy-website.sh`; vhost in `ops/deployment/nginx-marketplace.conf` |

> Server facts below are **reported** (from owner-run output recorded in this repo, Oct–Nov 2026) and have not been re-verified. See the [audit pack](../../docs/infrastructure-audit/16_AUDIT_EXECUTIVE_SUMMARY.md).

## Open points

- Same product decision as the portal (D-08).
- Marketplace listings are writable across companies in the Odoo module (ODOO-08).
