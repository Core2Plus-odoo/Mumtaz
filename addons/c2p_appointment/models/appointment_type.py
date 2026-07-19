import pytz
from datetime import datetime, timedelta, time

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class C2PAppointmentType(models.Model):
    _name = "c2p.appointment.type"
    _description = "Appointment Type"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    slug = fields.Char(
        string="URL Slug", required=True, copy=False,
        help="Used in the public URL, e.g. 'discovery-call' -> /appointment/discovery-call",
    )
    description = fields.Html(string="Description", translate=True)

    duration = fields.Float(
        string="Duration (hours)", default=0.5, required=True,
        help="Length of the appointment in hours. 0.5 = 30 minutes.",
    )
    buffer_after = fields.Float(
        string="Buffer After (hours)", default=0.0,
        help="Gap enforced after each appointment before the next slot is offered.",
    )
    min_lead_hours = fields.Integer(
        string="Minimum Notice (hours)", default=4,
        help="Bookings must be at least this far in the future.",
    )
    max_days_ahead = fields.Integer(
        string="Bookable Window (days)", default=30,
        help="How far ahead visitors can book.",
    )
    slot_interval = fields.Float(
        string="Slot Interval (hours)", default=0.5,
        help="Spacing between offered start times.",
    )

    staff_ids = fields.Many2many(
        "res.users", string="Available Staff", required=True,
        domain=[("share", "=", False)],
        help="Bookings are assigned to whichever selected staff member is free.",
    )
    resource_calendar_id = fields.Many2one(
        "resource.calendar", string="Working Hours",
        help="Working hours that define bookable times. Falls back to the company schedule.",
    )
    tz = fields.Selection(
        lambda self: [(t, t) for t in pytz.all_timezones],
        string="Timezone", default="Asia/Dubai", required=True,
    )

    location = fields.Char(string="Location", default="Online — link sent on confirmation")
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    is_published = fields.Boolean(string="Published", default=True)
    booking_count = fields.Integer(compute="_compute_booking_count")

    _sql_constraints = [
        ("slug_uniq", "unique(slug)", "The URL slug must be unique."),
    ]

    @api.constrains("duration", "slot_interval")
    def _check_durations(self):
        for rec in self:
            if rec.duration <= 0:
                raise ValidationError(_("Duration must be greater than zero."))
            if rec.slot_interval <= 0:
                raise ValidationError(_("Slot interval must be greater than zero."))

    def _compute_booking_count(self):
        data = self.env["c2p.appointment.booking"].read_group(
            [("appointment_type_id", "in", self.ids)],
            ["appointment_type_id"], ["appointment_type_id"])
        counts = {d["appointment_type_id"][0]: d["appointment_type_id_count"] for d in data}
        for rec in self:
            rec.booking_count = counts.get(rec.id, 0)

    def action_view_bookings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bookings — %s") % self.name,
            "res_model": "c2p.appointment.booking",
            "view_mode": "list,form",
            "domain": [("appointment_type_id", "=", self.id)],
            "context": {"default_appointment_type_id": self.id},
        }

    # ── availability ──────────────────────────────────────────────────────

    def _get_calendar(self):
        self.ensure_one()
        return self.resource_calendar_id or self.company_id.resource_calendar_id

    def _working_intervals(self, day, tzinfo):
        """Return list of (start_float, end_float) working periods for a weekday."""
        cal = self._get_calendar()
        if not cal:
            return [(9.0, 17.0)]
        dow = str(day.weekday())
        lines = cal.attendance_ids.filtered(lambda a: a.dayofweek == dow)
        return [(l.hour_from, l.hour_to) for l in lines] or []

    def _busy_periods(self, staff, day_start_utc, day_end_utc):
        """Existing calendar events for a staff member within the window."""
        events = self.env["calendar.event"].sudo().search([
            ("start", "<", fields.Datetime.to_string(day_end_utc)),
            ("stop", ">", fields.Datetime.to_string(day_start_utc)),
            ("partner_ids", "in", staff.partner_id.ids),
        ])
        return [(e.start, e.stop) for e in events]

    def get_available_slots(self, date_str):
        """Return list of dicts describing free slots on a given local date."""
        self.ensure_one()
        tzinfo = pytz.timezone(self.tz)
        try:
            day = fields.Date.from_string(date_str)
        except Exception:
            return []

        now_utc = datetime.utcnow()
        earliest = now_utc + timedelta(hours=self.min_lead_hours)
        latest = now_utc + timedelta(days=self.max_days_ahead)

        day_start_local = tzinfo.localize(datetime.combine(day, time(0, 0)))
        day_end_local = day_start_local + timedelta(days=1)
        day_start_utc = day_start_local.astimezone(pytz.utc).replace(tzinfo=None)
        day_end_utc = day_end_local.astimezone(pytz.utc).replace(tzinfo=None)

        if day_end_utc < earliest or day_start_utc > latest:
            return []

        intervals = self._working_intervals(day, tzinfo)
        if not intervals:
            return []

        # pre-load busy periods per staff member
        busy_by_staff = {
            s.id: self._busy_periods(s, day_start_utc, day_end_utc)
            for s in self.staff_ids
        }

        slots = []
        block = self.duration + self.buffer_after
        for hour_from, hour_to in intervals:
            cursor = hour_from
            while cursor + self.duration <= hour_to + 1e-6:
                h = int(cursor)
                m = int(round((cursor - h) * 60))
                if m == 60:
                    h, m = h + 1, 0
                try:
                    local_start = tzinfo.localize(datetime.combine(day, time(h, m)))
                except Exception:
                    cursor += self.slot_interval
                    continue
                start_utc = local_start.astimezone(pytz.utc).replace(tzinfo=None)
                stop_utc = start_utc + timedelta(hours=self.duration)

                if start_utc < earliest or start_utc > latest:
                    cursor += self.slot_interval
                    continue

                free_staff = None
                for s in self.staff_ids:
                    clash = any(
                        (start_utc < b_stop and stop_utc > b_start)
                        for b_start, b_stop in busy_by_staff.get(s.id, [])
                    )
                    if not clash:
                        free_staff = s
                        break

                if free_staff:
                    slots.append({
                        "start_utc": fields.Datetime.to_string(start_utc),
                        "label": local_start.strftime("%H:%M"),
                        "staff_id": free_staff.id,
                        "staff_name": free_staff.name,
                    })
                cursor += self.slot_interval
        return slots

    def get_available_days(self):
        """Which dates in the window have at least one free slot."""
        self.ensure_one()
        tzinfo = pytz.timezone(self.tz)
        today_local = datetime.now(tzinfo).date()
        out = []
        for i in range(0, self.max_days_ahead + 1):
            d = today_local + timedelta(days=i)
            if self.get_available_slots(fields.Date.to_string(d)):
                out.append(fields.Date.to_string(d))
        return out
