from odoo import api, fields, models


class FaizyWorker(models.Model):
    """A vetted on-ground worker in Pakistan — a "Faizy".

    `user_id` is optional on purpose: a Faizy exists as an operational record
    from the moment ops approves them, which is before they have ever logged in.
    """

    _name = "faizy.worker"
    _description = "Faizy (Ground Worker)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _rec_names_search = ["name", "phone", "cnic"]

    # Marks records created by the sample-data loader so they can all be
    # removed together without touching anything real.
    is_sample = fields.Boolean(default=False, copy=False, index=True)

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.worker") or "/",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        help="Vendor contact used for payouts and bills.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Portal User",
        help="Linked once the Faizy signs into the worker portal.",
    )
    phone = fields.Char(required=True, tracking=True)
    email = fields.Char()
    cnic = fields.Char(string="CNIC", tracking=True)

    city = fields.Char(required=True, index=True, tracking=True)
    area_ids = fields.Many2many("faizy.area", string="Areas Covered")
    service_ids = fields.Many2many("faizy.service", string="Services")

    state = fields.Selection(
        [
            ("applicant", "Applicant"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("inactive", "Inactive"),
        ],
        default="applicant",
        required=True,
        tracking=True,
        index=True,
    )
    # Assignment only considers workers who are both active AND available.
    is_available = fields.Boolean(
        string="Available",
        tracking=True,
        help="The Faizy's own on/off switch for taking new work.",
    )
    image_128 = fields.Image(max_width=128, max_height=128)
    date_joined = fields.Date(default=fields.Date.context_today)
    active = fields.Boolean(default=True)

    base_rate = fields.Monetary(
        currency_field="currency_id",
        help="Default payout per completed order.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    order_ids = fields.One2many("faizy.order", "worker_id")
    order_count = fields.Integer(compute="_compute_stats")
    completed_count = fields.Integer(compute="_compute_stats", store=True)
    cancelled_count = fields.Integer(compute="_compute_stats", store=True)
    # `aggregator` (not the pre-18 `group_operator`) — averaging is the only
    # sensible roll-up for a rating in list/pivot views.
    rating_avg = fields.Float(
        compute="_compute_stats", store=True, digits=(3, 2), aggregator="avg"
    )
    rating_count = fields.Integer(compute="_compute_stats", store=True)

    _sql_phone_unique = models.Constraint(
        "unique(phone)", "A Faizy with this phone number already exists."
    )

    @api.depends("order_ids.state", "order_ids.rating")
    def _compute_stats(self):
        for worker in self:
            orders = worker.order_ids
            completed = orders.filtered(lambda o: o.state == "completed")
            rated = completed.filtered(lambda o: o.rating)
            worker.order_count = len(orders)
            worker.completed_count = len(completed)
            worker.cancelled_count = len(orders.filtered(lambda o: o.state == "cancelled"))
            worker.rating_count = len(rated)
            worker.rating_avg = (
                sum(int(o.rating) for o in rated) / len(rated) if rated else 0.0
            )

    def action_set_active(self):
        self.write({"state": "active"})

    def action_suspend(self):
        self.write({"state": "suspended", "is_available": False})

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Orders"),
            "res_model": "faizy.order",
            "view_mode": "list,form",
            "domain": [("worker_id", "=", self.id)],
        }


class FaizyArea(models.Model):
    """A serviceable area within a city. Records rather than free text so
    coverage can be matched against a member's location when assigning."""

    _name = "faizy.area"
    _description = "Faizy Coverage Area"
    _order = "city, name"

    name = fields.Char(required=True)
    city = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)

    _sql_area_unique = models.Constraint(
        "unique(name, city)", "That area already exists for this city."
    )

    @api.depends("name", "city")
    def _compute_display_name(self):
        for area in self:
            area.display_name = f"{area.name}, {area.city}"


class FaizyService(models.Model):
    """A category of care work. Drives what a Faizy can be assigned and what the
    customer can book."""

    _name = "faizy.service"
    _description = "Faizy Service"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    icon = fields.Char(help="Emoji or font-awesome class shown in the portal.")
    # Counts against the monthly allowance. Some services (e.g. an emergency
    # welfare check) may be excluded from metering as a goodwill policy.
    consumes_activity = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

    _sql_code_unique = models.Constraint(
        "unique(code)", "Service codes must be unique."
    )
