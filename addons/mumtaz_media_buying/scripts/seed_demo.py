# -*- coding: utf-8 -*-
"""
Demo seeder for mumtaz_media_buying — populates realistic vendors, outlets,
rate cards, clients and approved media plans so the CEO Dashboard shows live
data instead of the built-in sample.

Run it with Odoo's shell (NOT imported by the module):

    sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d Mumtaz_IG2 \\
        --no-http < /opt/mumtaz/addons/mumtaz_media_buying/scripts/seed_demo.py

Idempotent: existing records (matched by name / campaign) are reused, so it is
safe to run more than once. Everything it creates is tagged "[MB-DEMO]" in the
partner note for easy identification.
"""
import datetime

MARK = "[MB-DEMO]"
Partner = env["res.partner"]
Outlet = env["media.outlet"]
Card = env["media.rate.card"]
Plan = env["media.plan"]


def vendor(name):
    rec = Partner.search(
        [("name", "=", name), ("is_media_vendor", "=", True)], limit=1)
    if not rec:
        rec = Partner.create({
            "name": name, "is_media_vendor": True,
            "is_company": True, "comment": MARK})
    return rec


def client(name):
    rec = Partner.search(
        [("name", "=", name), ("is_media_vendor", "=", False)], limit=1)
    if not rec:
        rec = Partner.create({
            "name": name, "is_company": True, "comment": MARK})
    return rec


def outlet(name, channel, ven):
    rec = Outlet.search([("name", "=", name)], limit=1)
    if not rec:
        rec = Outlet.create({
            "name": name, "channel": channel, "vendor_id": ven.id})
    return rec


def rate_card(name, ven, lines):
    rec = Card.search([("name", "=", name)], limit=1)
    if rec:
        return rec
    rec = Card.create({
        "name": name, "vendor_id": ven.id,
        "date_from": datetime.date(2026, 1, 1),
        "date_to": datetime.date(2026, 12, 31),
        "line_ids": [(0, 0, {
            "outlet_id": o.id, "name": fmt, "unit": unit, "rate": rate,
            "gross_rate": rate * 1.2,
        }) for (o, fmt, unit, rate) in lines],
    })
    rec.action_activate()
    return rec


def plan(campaign, cl, d_from, d_to, commission, fee, placements, running=False):
    rec = Plan.search([("campaign", "=", campaign)], limit=1)
    if rec:
        return rec
    rec = Plan.create({
        "campaign": campaign, "client_id": cl.id,
        "date_from": d_from, "date_to": d_to,
        "commission_percent": commission, "service_fee": fee,
        "line_ids": [(0, 0, {
            "outlet_id": o.id, "description": desc,
            "qty": qty, "unit_rate": rate,
        }) for (o, desc, qty, rate) in placements],
    })
    rec.action_approve()
    if running:
        rec.action_start()
    return rec


# ── vendors & outlets ────────────────────────────────────────────────────
geo = vendor("GEO Network")
ary = vendor("ARY Digital")
meta = vendor("Meta")
dawn = vendor("Dawn Media")
outdoor = vendor("Adverts Outdoor")

geo_tv = outlet("GEO TV", "tv", geo)
ary_tv = outlet("ARY News", "tv", ary)
meta_feed = outlet("Meta Feed", "digital", meta)
dawn_paper = outlet("Dawn Newspaper", "print", dawn)
board_m2 = outlet("Billboard M-2 Motorway", "ooh", outdoor)

# ── rate cards (rates in PKR) ────────────────────────────────────────────
rate_card("GEO Network — 2026", geo, [
    (geo_tv, "30-sec prime-time spot", "spot", 250000)])
rate_card("ARY Digital — 2026", ary, [
    (ary_tv, "30-sec spot", "spot", 180000)])
rate_card("Meta — 2026", meta, [
    (meta_feed, "Feed CPM (per 1k impressions)", "cpm", 1200)])
rate_card("Dawn Media — 2026", dawn, [
    (dawn_paper, "Full page colour", "insertion", 900000)])
rate_card("Adverts Outdoor — 2026", outdoor, [
    (board_m2, "Site / month", "site_month", 650000)])

# ── clients ──────────────────────────────────────────────────────────────
unilever = client("Unilever Pakistan")
telenor = client("Telenor")
alfalah = client("Bank Alfalah")
coke = client("Coca-Cola")
kn = client("K&N's Foods")

D = datetime.date

# ── media plans spread across the year (amounts land in the millions) ─────
plan("Summer Refresh 2026", unilever, D(2026, 5, 1), D(2026, 8, 31), 15, 200000, [
    (geo_tv, "Prime spots", 32, 250000),
    (meta_feed, "Feed impressions (k)", 2400, 1200),
], running=True)

plan("5G Nationwide Launch", telenor, D(2026, 3, 1), D(2026, 6, 30), 15, 350000, [
    (ary_tv, "News spots", 40, 180000),
    (board_m2, "Motorway sites", 4, 650000),
    (meta_feed, "Feed impressions (k)", 1800, 1200),
], running=True)

plan("Ramadan Banking", alfalah, D(2026, 2, 1), D(2026, 4, 30), 12, 150000, [
    (geo_tv, "Prime spots", 24, 250000),
    (dawn_paper, "Full pages", 6, 900000),
], running=True)

plan("Zero Sugar", coke, D(2026, 4, 1), D(2026, 7, 31), 15, 120000, [
    (meta_feed, "Feed impressions (k)", 1500, 1200),
    (board_m2, "Motorway sites", 3, 650000),
], running=True)

plan("Eid Feast", kn, D(2026, 3, 15), D(2026, 5, 15), 14, 90000, [
    (geo_tv, "Prime spots", 20, 250000),
], running=True)

plan("Monsoon Drive", unilever, D(2026, 6, 1), D(2026, 9, 30), 15, 180000, [
    (ary_tv, "News spots", 28, 180000),
    (board_m2, "Motorway sites", 3, 650000),
])

env.cr.commit()
n = Plan.search_count([("state", "in", ("approved", "running", "done"))])
print("[MB-DEMO] Seed complete — %d active media plans; open the CEO Dashboard." % n)
