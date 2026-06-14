"""Gated monkeypatch of odoo.http.db_filter for database-per-tenant routing.

DISABLED by default. When the env var MUMTAZ_DBFILTER_ROUTING=1 is set, an
incoming host like ``acme.erp.mumtaz.digital`` (or a tenant custom domain) is
resolved against the control database's ``mumtaz_tenant`` registry and Odoo is
restricted to that tenant's database. Suspended/archived tenants do not resolve.

When the flag is unset, the wrapper delegates to the original db_filter, so the
behaviour is byte-for-byte identical to stock Odoo.
"""
import logging
import os

import odoo
import odoo.http as ohttp
import odoo.sql_db
from odoo.tools import config

_logger = logging.getLogger(__name__)

_original_db_filter = ohttp.db_filter


def _enabled():
    return os.environ.get("MUMTAZ_DBFILTER_ROUTING") == "1"


def _control_db():
    """Database holding the mumtaz_tenant registry."""
    db = os.environ.get("MUMTAZ_CONTROL_DB")
    if db:
        return db
    names = config.get("db_name") or ""
    first = names.split(",")[0].strip()
    return first or None


def _base_domain():
    return (os.environ.get("MUMTAZ_ERP_BASE_DOMAIN")
            or "erp.mumtaz.digital").strip(".").lower()


def _host_from_request(host):
    if host:
        return host
    try:
        return ohttp.request.httprequest.environ.get("HTTP_HOST", "") or ""
    except Exception:  # noqa: BLE001 - no active request
        return ""


def _resolve_db(host):
    control = _control_db()
    if not control:
        return None
    h = (host or "").split(":")[0].lower().strip(".")
    if not h:
        return None
    base = _base_domain()
    if h == base:
        return None
    sub = None
    if h.endswith("." + base):
        sub = h[: -(len(base) + 1)].split(".")[-1]
    try:
        cnx = odoo.sql_db.db_connect(control)
        with cnx.cursor() as cr:
            if sub:
                cr.execute(
                    "SELECT database_name FROM mumtaz_tenant "
                    "WHERE state = 'active' AND subdomain = %s LIMIT 1",
                    (sub,),
                )
                row = cr.fetchone()
                if row and row[0]:
                    return row[0]
            cr.execute(
                "SELECT database_name FROM mumtaz_tenant "
                "WHERE state = 'active' AND custom_domain = %s LIMIT 1",
                (h,),
            )
            row = cr.fetchone()
            return row[0] if (row and row[0]) else None
    except Exception:  # noqa: BLE001 - never break DB selection
        _logger.exception("Mumtaz routing: host resolution failed for %s", h)
        return None


def _mumtaz_db_filter(dbs, host=None):
    if not _enabled():
        return _original_db_filter(dbs, host=host)
    target = _resolve_db(_host_from_request(host))
    if target:
        return [d for d in dbs if d == target]
    # Unknown/suspended host: fall back to stock filtering.
    return _original_db_filter(dbs, host=host)


def apply():
    # Installing the wrapper unconditionally is safe: when disabled it simply
    # delegates. This lets the env flag be toggled with a restart (no reinstall).
    if ohttp.db_filter is _mumtaz_db_filter:
        return
    ohttp.db_filter = _mumtaz_db_filter
    if _enabled():
        _logger.info("Mumtaz subdomain db routing ACTIVE (base=%s, control_db=%s).",
                     _base_domain(), _control_db())
    else:
        _logger.info("Mumtaz subdomain db routing installed but DISABLED "
                     "(set MUMTAZ_DBFILTER_ROUTING=1 to activate).")
