from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class FaizyOrder(models.Model):
    """A care task: groceries, a medicine run, a doctor visit, a document errand.

    Money is computed here, never entered. The customer says what was bought;
    the platform fee, the vendor commission and the total are derived from it.
    The rates live on the company so ops can change policy without a developer.
    """

    _name = "faizy.order"
    _description = "Faizy Care Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_names_search = ["name", "title"]

    # Marks records created by the sample-data loader so they can all be
    # removed together without touching anything real.
    is_sample = fields.Boolean(default=False, copy=False, index=True)

    name = fields.Char(
        string="Order Reference",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.order") or "/",
    )
    title = fields.Char(required=True, tracking=True)
    description = fields.Text()

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, index=True, tracking=True
    )
    family_member_id = fields.Many2one(
        "faizy.family.member",
        string="For",
        index=True,
        domain="[('partner_id', '=', partner_id)]",
        help="Who the errand is for. Leave empty for the household generally.",
    )
    fmb_id = fields.Char(related="family_member_id.fmb_id", store=True, string="FMB ID")
    service_id = fields.Many2one("faizy.service", required=True, tracking=True)

    worker_id = fields.Many2one(
        "faizy.worker",
        string="Assigned Faizy",
        index=True,
        tracking=True,
        domain="[('state', '=', 'active')]",
    )
    city = fields.Char(required=True, index=True)
    street = fields.Char()

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("assigned", "Assigned"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
        group_expand="_group_expand_state",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgent")], default="0", tracking=True
    )

    scheduled_date = fields.Datetime(tracking=True)

    # ── Recurring bookings ───────────────────────────────────────────────
    # Groceries every Friday, medicines on the 1st. Each occurrence is a real
    # order so it can be assigned, priced and rated independently; the template
    # only decides when the next one appears.
    is_recurring = fields.Boolean(
        string="Repeats",
        help="Generate a fresh order automatically on a schedule.",
    )
    recurrence_type = fields.Selection(
        [("weekly", "Weekly"), ("monthly", "Monthly")],
        default="weekly",
    )
    recurrence_interval = fields.Integer(
        string="Every",
        default=1,
        help="1 = every week/month, 2 = every other, and so on.",
    )
    recurrence_next_date = fields.Date(
        string="Next Occurrence",
        index=True,
        help="When the next order will be created. Cleared to stop repeating.",
    )
    recurrence_end_date = fields.Date(string="Repeat Until")
    parent_order_id = fields.Many2one(
        "faizy.order", string="Repeats From", index=True, ondelete="set null"
    )
    child_order_ids = fields.One2many("faizy.order", "parent_order_id")
    occurrence_count = fields.Integer(compute="_compute_occurrence_count")

    date_assigned = fields.Datetime(readonly=True, copy=False)
    date_started = fields.Datetime(readonly=True, copy=False)
    date_completed = fields.Datetime(readonly=True, copy=False)
    cancellation_reason = fields.Text()

    # Hides the member's identity and notes from the assigned Faizy.
    privacy_mode = fields.Boolean(
        string="Private",
        help="The Faizy sees the task and address but not the member's name, "
        "phone or notes.",
    )

    # ── Money ────────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )
    purchase_value = fields.Monetary(
        currency_field="currency_id",
        tracking=True,
        help="What the customer's money bought — groceries, medicine, and so on.",
    )
    service_fee = fields.Monetary(
        currency_field="currency_id",
        help="Charge for running the errand.",
    )
    platform_fee = fields.Monetary(
        compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        domain=[("supplier_rank", ">", 0)],
        help="Set when a third party fulfils the order. Triggers commission.",
    )
    vendor_commission = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
        help="Retained from the vendor. Revenue to Faizy — NOT charged to the "
        "customer, so it is excluded from the total below.",
    )
    amount_total = fields.Monetary(
        string="Customer Total",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    consumed_activity = fields.Boolean(readonly=True, copy=False)
    activity_source = fields.Selection(
        [("free", "Free Grant"), ("included", "Plan Allowance"), ("overage", "Overage")],
        readonly=True,
        copy=False,
    )

    # ── Delivery & feedback ──────────────────────────────────────────────
    proof_image = fields.Image(
        string="Proof of Delivery",
        max_width=1920,
        max_height=1920,
        help="Photo captured by the Faizy on completion.",
    )
    completion_note = fields.Text()
    rating = fields.Selection(
        [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5")],
        tracking=True,
    )
    rating_comment = fields.Text()

    @api.model
    def _group_expand_state(self, states, domain):
        """Keep every kanban column visible even when empty — an ops board that
        hides 'Pending' the moment it clears is disorienting."""
        return [key for key, _label in self._fields["state"].selection]

    @api.depends("purchase_value", "service_fee", "vendor_id", "company_id")
    def _compute_amounts(self):
        for order in self:
            company = order.company_id or self.env.company
            platform_rate = company.faizy_platform_fee_rate
            commission_rate = company.faizy_vendor_commission_rate

            order.platform_fee = order.currency_id.round(
                order.purchase_value * platform_rate
            )
            order.vendor_commission = (
                order.currency_id.round(order.purchase_value * commission_rate)
                if order.vendor_id
                else 0.0
            )
            # The customer pays for goods + platform fee + service. Vendor
            # commission is retained on the vendor side and deliberately absent.
            order.amount_total = (
                order.purchase_value + order.platform_fee + order.service_fee
            )

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )

    # ── Workflow ─────────────────────────────────────────────────────────

    def action_assign(self):
        """Assign to a Faizy and notify both sides."""
        for order in self:
            if not order.worker_id:
                raise UserError(
                    self.env._("Pick a Faizy before assigning %(ref)s.", ref=order.name)
                )
            order.write(
                {"state": "assigned", "date_assigned": fields.Datetime.now()}
            )
            order._notify_whatsapp("faizy_assigned")

    def action_start(self):
        self.write({"state": "in_progress", "date_started": fields.Datetime.now()})
        self._notify_whatsapp("status_update")

    def action_complete(self):
        for order in self:
            order.write(
                {"state": "completed", "date_completed": fields.Datetime.now()}
            )
            order._notify_whatsapp("status_update")
            order._notify_whatsapp("receipt")

    def action_cancel(self):
        self.write({"state": "cancelled"})
        self._notify_whatsapp("status_update")

    def action_reset_to_pending(self):
        self.write({"state": "pending", "worker_id": False, "date_assigned": False})

    def action_confirm(self):
        """Accept the booking: meter the activity, then notify the customer.

        This is the paywall. If the customer has no free activities left and no
        live subscription, the booking is refused here rather than silently
        delivered for nothing.
        """
        for order in self:
            if order.consumed_activity or not order.service_id.consumes_activity:
                order._notify_whatsapp("booking_confirmation")
                continue

            subscription = order.partner_id.faizy_subscription_id
            if order.partner_id.faizy_free_activities <= 0 and not subscription:
                raise UserError(
                    self.env._(
                        "%(customer)s has used their free activities and has no "
                        "active subscription. Start a plan before booking.",
                        customer=order.partner_id.display_name,
                    )
                )

            source = (
                subscription.consume_activity(order=order)
                if subscription
                else order._consume_free_activity()
            )
            order.write({"consumed_activity": True, "activity_source": source})
            order._notify_whatsapp("booking_confirmation")

    def _consume_free_activity(self):
        """Spend one of the signup grant when there is no subscription yet."""
        self.ensure_one()
        self.partner_id.sudo().faizy_free_activities -= 1
        self.env["faizy.activity.log"].sudo().create(
            {
                "partner_id": self.partner_id.id,
                "order_id": self.id,
                "source": "free",
                "amount": 0.0,
                "currency_id": self.currency_id.id,
            }
        )
        return "free"

    # ── Notifications ────────────────────────────────────────────────────

    def _notify_whatsapp(self, message_type):
        """Queue the outbound WhatsApp message(s) for this transition.

        Queued as records first, sent by cron — a failed send stays visible and
        retryable instead of disappearing.
        """
        Queue = self.env["faizy.whatsapp.message"].sudo()
        for order in self:
            if order.partner_id.mobile or order.partner_id.phone:
                Queue.queue_message(
                    partner=order.partner_id,
                    message_type=message_type,
                    order=order,
                )
            # The worker's assignment message. This is also the WhatsApp-only
            # path for Faizies who never install the portal.
            if message_type == "faizy_assigned" and order.worker_id.phone:
                Queue.queue_message(
                    worker=order.worker_id,
                    message_type="worker_assignment",
                    order=order,
                )

    @api.depends("child_order_ids")
    def _compute_occurrence_count(self):
        for order in self:
            order.occurrence_count = len(order.child_order_ids)

    def action_view_occurrences(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Occurrences"),
            "res_model": "faizy.order",
            "view_mode": "list,form",
            "domain": [("parent_order_id", "=", self.id)],
        }

    @api.model
    def _cron_generate_recurring(self):
        """Create the next occurrence of each due recurring order.

        Copies the request, not the outcome: the new order starts pending and
        unassigned, with no proof, rating or money carried over. Only the
        template advances its own next date, so a chain cannot fork.
        """
        today = fields.Date.context_today(self)
        due = self.search(
            [
                ("is_recurring", "=", True),
                ("recurrence_next_date", "!=", False),
                ("recurrence_next_date", "<=", today),
                ("parent_order_id", "=", False),
            ]
        )

        for template in due:
            if template.recurrence_end_date and template.recurrence_next_date > template.recurrence_end_date:
                template.recurrence_next_date = False
                continue

            self.create(
                {
                    "title": template.title,
                    "description": template.description,
                    "partner_id": template.partner_id.id,
                    "family_member_id": template.family_member_id.id,
                    "service_id": template.service_id.id,
                    "city": template.city,
                    "street": template.street,
                    "privacy_mode": template.privacy_mode,
                    "service_fee": template.service_fee,
                    "currency_id": template.currency_id.id,
                    "scheduled_date": template.recurrence_next_date,
                    "parent_order_id": template.id,
                }
            )

            step = template.recurrence_interval or 1
            delta = (
                relativedelta(weeks=step)
                if template.recurrence_type == "weekly"
                else relativedelta(months=step)
            )
            template.recurrence_next_date = template.recurrence_next_date + delta

        return True

    @api.onchange("family_member_id")
    def _onchange_family_member_id(self):
        if self.family_member_id:
            self.city = self.family_member_id.city
            self.street = self.family_member_id.street

    @api.depends("name", "title")
    def _compute_display_name(self):
        for order in self:
            order.display_name = f"{order.name} — {order.title or ''}".strip(" —")
