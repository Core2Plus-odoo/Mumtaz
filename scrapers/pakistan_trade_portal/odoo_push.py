import logging
from typing import Dict, Iterable, List
from xmlrpc import client

_LOGGER = logging.getLogger(__name__)


class OdooPushError(Exception):
    """Raised when connection/authentication to Odoo fails."""


def _require_config(config: Dict[str, str]) -> None:
    required = ["url", "db", "username", "password"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise OdooPushError(f"Missing Odoo config keys: {', '.join(missing)}")


def _connect(config: Dict[str, str]):
    _require_config(config)
    common_proxy = client.ServerProxy(f"{config['url'].rstrip('/')}/xmlrpc/2/common")
    uid = common_proxy.authenticate(config["db"], config["username"], config["password"], {})
    if not uid:
        raise OdooPushError("Authentication failed for provided Odoo credentials")

    object_proxy = client.ServerProxy(f"{config['url'].rstrip('/')}/xmlrpc/2/object")
    return uid, object_proxy


def _lead_vals(row: Dict[str, object]) -> Dict[str, object]:
    name = (row.get("company_name") or row.get("product_name") or "Website Lead").strip()
    contact_name = (row.get("company_name") or "").strip()

    description_parts: List[str] = []
    for key in ("description", "sector", "subcategory", "source_url", "social_links"):
        value = (row.get(key) or "").strip()
        if value:
            description_parts.append(f"{key}: {value}")

    return {
        "name": name,
        "type": "lead",
        "partner_name": contact_name or False,
        "email_from": (row.get("contact_email") or "").strip() or False,
        "phone": (row.get("contact_phone") or "").strip() or False,
        "city": (row.get("city") or "").strip() or False,
        "contact_name": contact_name or False,
        "website": (row.get("website") or row.get("company_url") or "").strip() or False,
        "description": "\n".join(description_parts) if description_parts else False,
    }


def push_leads_to_odoo(rows: Iterable[Dict[str, object]], config: Dict[str, str]) -> List[int]:
    """Create crm.lead records in Odoo and return created IDs."""
    uid, object_proxy = _connect(config)
    created_ids: List[int] = []

    for row in rows:
        vals = _lead_vals(row)
        if not vals["name"]:
            _LOGGER.warning("Skipping row with empty lead name: %s", row)
            continue
        lead_id = object_proxy.execute_kw(
            config["db"],
            uid,
            config["password"],
            "crm.lead",
            "create",
            [vals],
        )
        created_ids.append(lead_id)
        _LOGGER.info("Created crm.lead ID=%s for source=%s", lead_id, row.get("source_url"))

    return created_ids
