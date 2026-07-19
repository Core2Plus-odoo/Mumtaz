import uuid
import pytz
from datetime import timedelta

from odoo import api, fields, models, _


class C2PAppointmentBooking(models.Model):
    _name = "c2p.appointment.booking"
    _description = "Appointment Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)

    appointment_type_id = fields.Many2one(
        "c2p.appointment.type", string="Appointment Type",
        required=True, ondelete="restrict", tracking=True)
    staff_id = fields.Many2one("res.users", string="Assigned To", tracking=True)

    name = fields.Char(string="Name", required=True, tracking=True)
    email = fields.Char(string="Email", required=True, tracking=True)
    phone = fields.Char(string="Phone", tracking=True)
    company_name = fields.Char(string="Company")
    notes = fields.Text(string="What would you like to discuss?")

    start_datetime = fields.Datetime(string="Start", required=True, tracking=True)
    stop_datetime = fields.Datetime(string="End", compute="_compute_stop", store=True)
    duration = fields.Float(related="appointment_type_id.duration", store=True)

    state = fields.Selection([
        ("confirmed", "Confirmed"),
        ("attended", "Attended"),
        ("no_show", "No Show"),
        ("cancelled", "Cancelled"),
    ], default="confirmed", required=True, tracking=True)

    access_token = fields.Char(default=lambda s: uuid.uuid4().hex, copy=False, readonly=True)
    calendar_event_id = fields.Many2one("calendar.event", string="Calendar Event", ondelete="set null")
    lead_id = fields.Many2one("crm.lead", string="CRM Lead", ondelete="set null")
    partner_id = fields.Many2one("res.partner", string="Contact")

    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)

    @api.depends("name", "appointment_type_id", "start_datetime")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _("Booking")]
            if rec.appointment_type_id:
                parts.append(rec.appointment_type_id.name)
            rec.display_name = " — ".join(parts)

    @api.depends("start_datetime", "appointment_type_id.duration")
    def _compute_stop(self):
        for rec in self:
            if rec.start_datetime and rec.appointment_type_id:
                rec.stop_datetime = rec.start_datetime + timedelta(
                    hours=rec.appointment_type_id.duration)
            else:
                rec.stop_datetime = rec.start_datetime

    def local_start_string(self):
        """Human readable start time in the appointment type's timezone."""
        self.ensure_one()
        if not self.start_datetime:
            return ""
        tzinfo = pytz.timezone(self.appointment_type_id.tz or "UTC")
        local = pytz.utc.localize(self.start_datetime).astimezone(tzinfo)
        return local.strftime("%A %d %B %Y at %H:%M (%Z)")

    # ── lifecycle ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        bookings = super().create(vals_list)
        for b in bookings:
            b._sync_partner()
            b._create_calendar_event()
            b._create_lead()
            b._send_confirmation()
        return bookings

    def _sync_partner(self):
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("email", "=ilike", self.email)], limit=1)
        if not partner:
            partner = Partner.create({
                "name": self.name,
                "email": self.email,
                "phone": self.phone or False,
                "company_name": self.company_name or False,
            })
        elif self.phone and not partner.phone:
            partner.phone = self.phone
        self.partner_id = partner.id

    def _create_calendar_event(self):
        self.ensure_one()
        if self.calendar_event_id:
            return
        atype = self.appointment_type_id
        attendees = self.partner_id.ids
        if self.staff_id and self.staff_id.partner_id:
            attendees.append(self.staff_id.partner_id.id)
        event = self.env["calendar.event"].sudo().create({
            "name": _("%s — %s") % (atype.name, self.name),
            "start": self.start_datetime,
            "stop": self.stop_datetime,
            "duration": atype.duration,
            "partner_ids": [(6, 0, attendees)],
            "user_id": self.staff_id.id or self.env.uid,
            "location": atype.location or False,
            "description": self._event_description(),
        })
        self.calendar_event_id = event.id

    def _event_description(self):
        self.ensure_one()
        bits = [
            _("Booked via the website."),
            _("Contact: %s") % (self.name or ""),
            _("Email: %s") % (self.email or ""),
        ]
        if self.phone:
            bits.append(_("Phone: %s") % self.phone)
        if self.company_name:
            bits.append(_("Company: %s") % self.company_name)
        if self.notes:
            bits.append(_("Notes: %s") % self.notes)
        return "<br/>".join(bits)

    def _create_lead(self):
        self.ensure_one()
        if self.lead_id:
            return
        source = self.env["utm.source"].sudo().search(
            [("name", "=", "Website Appointment")], limit=1)
        if not source:
            source = self.env["utm.source"].sudo().create({"name": "Website Appointment"})
        vals = {
            "name": _("Appointment — %s") % (self.company_name or self.name),
            "contact_name": self.name,
            "partner_name": self.company_name or False,
            "email_from": self.email,
            "phone": self.phone or False,
            "description": self.notes or False,
            "type": "opportunity",
            "source_id": source.id,
            "partner_id": self.partner_id.id,
        }
        if self.staff_id:
            vals["user_id"] = self.staff_id.id
        lead = self.env["crm.lead"].sudo().create(vals)
        lead.message_post(body=_(
            "<b>Appointment booked</b><br/>Type: %s<br/>When: %s<br/>With: %s"
        ) % (self.appointment_type_id.name, self.local_start_string(),
             self.staff_id.name or _("Unassigned")))
        self.lead_id = lead.id

    def _send_confirmation(self):
        self.ensure_one()
        template = self.env.ref(
            "c2p_appointment.mail_template_appointment_confirmation",
            raise_if_not_found=False)
        if template:
            template.sudo().send_mail(self.id, force_send=False)

    def action_cancel(self):
        for rec in self:
            if rec.calendar_event_id:
                rec.calendar_event_id.sudo().unlink()
            rec.state = "cancelled"

    def action_mark_attended(self):
        self.write({"state": "attended"})

    def action_mark_no_show(self):
        self.write({"state": "no_show"})

    def action_view_lead(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
        }
