from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FaizyFamilyMember(models.Model):
    """A person back home that a customer is caring for.

    Every member gets a permanent FMB ID (FMB-000001). It is allocated from an
    Odoo sequence, never composed in the UI — the ID appears on bookings, in the
    admin, and in the worker's job sheet, so it has to be stable and unique.
    """

    _name = "faizy.family.member"
    _description = "Faizy Family Member"
    _inherit = ["mail.thread"]
    _order = "fmb_id"
    _rec_names_search = ["name", "fmb_id"]

    # Marks records created by the sample-data loader so they can all be
    # removed together without touching anything real.
    is_sample = fields.Boolean(default=False, copy=False, index=True)

    name = fields.Char(required=True, tracking=True)
    fmb_id = fields.Char(
        string="FMB ID",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.family.member")
        or "/",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="The subscriber in the Gulf who this member belongs to.",
    )
    relationship = fields.Selection(
        [
            ("mother", "Mother"),
            ("father", "Father"),
            ("sibling", "Sibling"),
            ("child", "Child"),
            ("grandparent", "Grandparent"),
            ("spouse", "Spouse"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    phone = fields.Char()
    date_of_birth = fields.Date()
    age = fields.Integer(compute="_compute_age")

    # Where the member actually lives — this drives which Faizy can be assigned.
    city = fields.Char(required=True, index=True)
    area = fields.Char()
    street = fields.Char()

    # Sensitive. Hidden from the assigned Faizy when an order is marked private.
    medical_notes = fields.Text(
        groups="faizy_core.group_faizy_ops",
        help="Allergies, conditions, regular medication. Restricted to ops.",
    )
    notes = fields.Text()
    image_128 = fields.Image(max_width=128, max_height=128)
    active = fields.Boolean(default=True)

    order_ids = fields.One2many("faizy.order", "family_member_id")

    # ── Care score ───────────────────────────────────────────────────────
    # The customer app's ring, and its algorithm exactly: how recently this
    # person was actually looked after. Nothing else — not spend, not order
    # count. A parent visited last week scores 100 whatever the plan says.
    care_score = fields.Integer(compute="_compute_care_score", store=True)
    care_score_state = fields.Selection(
        [("good", "Good"), ("fair", "Fair"), ("poor", "Needs Attention")],
        compute="_compute_care_score",
        store=True,
    )
    order_count = fields.Integer(compute="_compute_order_count")

    _sql_fmb_unique = models.Constraint(
        "unique(fmb_id)", "FMB IDs must be unique."
    )

    @api.depends("date_of_birth")
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for member in self:
            dob = member.date_of_birth
            if not dob:
                member.age = 0
                continue
            member.age = (
                today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            )

    @api.depends("order_ids.create_date")
    def _compute_care_score(self):
        """Days since this member's most recent order, banded.

        Taken verbatim from the prototype: 7 days -> 100, 14 -> 85, 21 -> 65,
        30 -> 45, beyond that 20, and 0 if nothing has ever been done for them.
        The bands are deliberately generous at the top — weekly contact is the
        product's promise, not daily.
        """
        now = fields.Datetime.now()
        for member in self:
            latest = max(
                (o.create_date for o in member.order_ids if o.create_date), default=None
            )
            if not latest:
                member.care_score = 0
                member.care_score_state = "poor"
                continue
            days = (now - latest).days
            member.care_score = (
                100 if days <= 7 else
                85 if days <= 14 else
                65 if days <= 21 else
                45 if days <= 30 else
                20
            )
            member.care_score_state = (
                "good" if member.care_score >= 80
                else "fair" if member.care_score >= 50
                else "poor"
            )

    @api.depends("order_ids")
    def _compute_order_count(self):
        data = self.env["faizy.order"]._read_group(
            [("family_member_id", "in", self.ids)],
            groupby=["family_member_id"],
            aggregates=["__count"],
        )
        counts = {member.id: count for member, count in data}
        for member in self:
            member.order_count = counts.get(member.id, 0)

    @api.constrains("partner_id")
    def _check_plan_member_limit(self):
        """Enforce the plan's family-member cap at the point of adding one."""
        for member in self:
            subscription = member.partner_id.faizy_subscription_id
            limit = subscription.plan_id.max_family_members if subscription else 0
            if not limit:
                continue
            used = self.search_count(
                [("partner_id", "=", member.partner_id.id), ("active", "=", True)]
            )
            if used > limit:
                raise ValidationError(
                    self.env._(
                        "The %(plan)s plan covers %(limit)s family members. "
                        "Upgrade the subscription to add more.",
                        plan=subscription.plan_id.name,
                        limit=limit,
                    )
                )

    @api.depends("name", "fmb_id")
    def _compute_display_name(self):
        for member in self:
            member.display_name = f"{member.name} ({member.fmb_id})"

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Orders"),
            "res_model": "faizy.order",
            "view_mode": "list,form",
            "domain": [("family_member_id", "=", self.id)],
            "context": {
                "default_family_member_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }
