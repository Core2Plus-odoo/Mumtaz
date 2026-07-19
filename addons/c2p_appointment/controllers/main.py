import pytz
from datetime import datetime, timedelta

from odoo import fields, http, _
from odoo.http import request


class C2PAppointmentController(http.Controller):

    # ── index: choose an appointment type ─────────────────────────────────
    @http.route(["/appointment"], type="http", auth="public", website=True, sitemap=True)
    def appointment_index(self, **kw):
        types = request.env["c2p.appointment.type"].sudo().search(
            [("is_published", "=", True)])
        if len(types) == 1:
            return request.redirect("/appointment/%s" % types.slug)
        return request.render("c2p_appointment.appointment_index", {
            "appointment_types": types,
        })

    # ── booking page for a given type ─────────────────────────────────────
    @http.route(["/appointment/<string:slug>"], type="http", auth="public",
                website=True, sitemap=True)
    def appointment_form(self, slug, **kw):
        atype = request.env["c2p.appointment.type"].sudo().search(
            [("slug", "=", slug), ("is_published", "=", True)], limit=1)
        if not atype:
            return request.not_found()
        tzinfo = pytz.timezone(atype.tz)
        today_local = datetime.now(tzinfo).date()
        max_date = today_local + timedelta(days=atype.max_days_ahead)
        return request.render("c2p_appointment.appointment_form", {
            "atype": atype,
            "min_date": fields.Date.to_string(today_local),
            "max_date": fields.Date.to_string(max_date),
        })

    # ── JSON: free slots for a date ───────────────────────────────────────
    @http.route(["/appointment/slots"], type="json", auth="public", website=True)
    def appointment_slots(self, type_id=None, date=None, **kw):
        if not type_id or not date:
            return {"slots": []}
        atype = request.env["c2p.appointment.type"].sudo().browse(int(type_id))
        if not atype.exists() or not atype.is_published:
            return {"slots": []}
        return {"slots": atype.get_available_slots(date), "tz": atype.tz}

    # ── JSON: which days have availability ────────────────────────────────
    @http.route(["/appointment/days"], type="json", auth="public", website=True)
    def appointment_days(self, type_id=None, **kw):
        if not type_id:
            return {"days": []}
        atype = request.env["c2p.appointment.type"].sudo().browse(int(type_id))
        if not atype.exists():
            return {"days": []}
        return {"days": atype.get_available_days()}

    # ── submit booking ────────────────────────────────────────────────────
    @http.route(["/appointment/book"], type="http", auth="public", website=True,
                methods=["POST"], csrf=True)
    def appointment_book(self, **post):
        required = ["type_id", "start_utc", "name", "email"]
        if not all(post.get(f) for f in required):
            return request.redirect("/appointment")

        atype = request.env["c2p.appointment.type"].sudo().browse(int(post["type_id"]))
        if not atype.exists() or not atype.is_published:
            return request.not_found()

        # re-validate the slot is still free
        start_utc = post["start_utc"]
        tzinfo = pytz.timezone(atype.tz)
        try:
            dt = fields.Datetime.from_string(start_utc)
        except Exception:
            return request.redirect("/appointment/%s?error=invalid" % atype.slug)
        local_date = pytz.utc.localize(dt).astimezone(tzinfo).date()
        available = atype.get_available_slots(fields.Date.to_string(local_date))
        match = next((s for s in available if s["start_utc"] == start_utc), None)
        if not match:
            return request.redirect("/appointment/%s?error=taken" % atype.slug)

        booking = request.env["c2p.appointment.booking"].sudo().create({
            "appointment_type_id": atype.id,
            "staff_id": match["staff_id"],
            "start_datetime": start_utc,
            "name": post.get("name"),
            "email": post.get("email"),
            "phone": post.get("phone"),
            "company_name": post.get("company_name"),
            "notes": post.get("notes"),
        })
        return request.redirect("/appointment/confirmed/%s" % booking.access_token)

    # ── confirmation page ─────────────────────────────────────────────────
    @http.route(["/appointment/confirmed/<string:token>"], type="http",
                auth="public", website=True, sitemap=False)
    def appointment_confirmed(self, token, **kw):
        booking = request.env["c2p.appointment.booking"].sudo().search(
            [("access_token", "=", token)], limit=1)
        if not booking:
            return request.not_found()
        return request.render("c2p_appointment.appointment_confirmed", {
            "booking": booking,
        })

    # ── cancel via token ──────────────────────────────────────────────────
    @http.route(["/appointment/cancel/<string:token>"], type="http",
                auth="public", website=True, sitemap=False)
    def appointment_cancel(self, token, **kw):
        booking = request.env["c2p.appointment.booking"].sudo().search(
            [("access_token", "=", token)], limit=1)
        if not booking:
            return request.not_found()
        if booking.state == "confirmed":
            booking.action_cancel()
        return request.render("c2p_appointment.appointment_cancelled", {
            "booking": booking,
        })

    # ── .ics download ─────────────────────────────────────────────────────
    @http.route(["/appointment/ics/<string:token>"], type="http",
                auth="public", website=True, sitemap=False)
    def appointment_ics(self, token, **kw):
        booking = request.env["c2p.appointment.booking"].sudo().search(
            [("access_token", "=", token)], limit=1)
        if not booking or not booking.start_datetime:
            return request.not_found()

        def fmt(dt):
            return dt.strftime("%Y%m%dT%H%M%SZ")

        summary = "%s — %s" % (booking.appointment_type_id.name,
                               booking.company_id.name or "C2P Group")
        desc = (booking.notes or "").replace("\n", "\\n")
        ics = "\r\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//C2P Group//Appointment//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            "UID:%s@core2plus.com" % booking.access_token,
            "DTSTAMP:%s" % fmt(datetime.utcnow()),
            "DTSTART:%s" % fmt(booking.start_datetime),
            "DTEND:%s" % fmt(booking.stop_datetime),
            "SUMMARY:%s" % summary,
            "DESCRIPTION:%s" % desc,
            "LOCATION:%s" % (booking.appointment_type_id.location or ""),
            "STATUS:CONFIRMED",
            "END:VEVENT",
            "END:VCALENDAR",
        ])
        return request.make_response(ics, headers=[
            ("Content-Type", "text/calendar; charset=utf-8"),
            ("Content-Disposition", 'attachment; filename="appointment.ics"'),
        ])
