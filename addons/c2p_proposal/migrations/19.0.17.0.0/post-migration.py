"""Backfill product categories on the curated C2P services.

The services were seeded (in a noupdate block) before their categories existed,
so existing installs still carry the default category. Re-slot each service
into its C2P category unless it has already been moved into a C2P category by
hand — manual categorisation is preserved.
"""
from odoo import SUPERUSER_ID, api

# service xml_id -> category xml_id
_MAP = {
    "svc_erp_impl": "categ_c2p_erp",
    "svc_discovery": "categ_c2p_advisory",
    "svc_finance": "categ_c2p_finance",
    "svc_bi": "categ_c2p_bi",
    "svc_migration": "categ_c2p_data",
    "svc_integration": "categ_c2p_data",
    "svc_custom": "categ_c2p_dev",
    "svc_training": "categ_c2p_support",
    "svc_support": "categ_c2p_support",
}


def _in_tree(categ, parent):
    """True if `categ` is `parent` or a descendant of it."""
    node = categ
    while node:
        if node == parent:
            return True
        node = node.parent_id
    return False


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    parent = env.ref("c2p_proposal.categ_c2p_services", raise_if_not_found=False)
    for svc_xmlid, categ_xmlid in _MAP.items():
        product = env.ref("c2p_proposal.%s" % svc_xmlid, raise_if_not_found=False)
        categ = env.ref("c2p_proposal.%s" % categ_xmlid, raise_if_not_found=False)
        if not product or not categ:
            continue
        # Only move it if it is not already inside the C2P Services tree
        # (so a manual re-categorisation is preserved).
        if not (parent and product.categ_id and _in_tree(product.categ_id, parent)):
            product.categ_id = categ.id
