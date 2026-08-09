from odoo import api, fields, models
from odoo.exceptions import UserError


class FaizyApplication(models.Model):
    """A worker application from the public onboarding wizard.

    Deliberately not tied to a user account — applicants have none yet. They
    track progress with the reference number (FZY-…) plus their phone, which is
    why the reference is generated and shown at submission.
    """

    _name = "faizy.application"
    _description = "Faizy Worker Application"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_names_search = ["reference", "name", "phone"]

    # Marks records created by the sample-data loader so they can all be
    # removed together without touching anything real.
    is_sample = fields.Boolean(default=False, copy=False, index=True)

    reference = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("faizy.application")
        or "/",
    )

    # Step 2 — personal
    name = fields.Char(string="Full Name", required=True, tracking=True)
    phone = fields.Char(required=True, tracking=True)
    cnic = fields.Char(string="CNIC", required=True, help="Format: 00000-0000000-0")
    email = fields.Char()
    date_of_birth = fields.Date()

    # Step 3 — location and coverage
    city = fields.Char(required=True, index=True)
    area_ids = fields.Many2many("faizy.area", string="Areas Covered")

    # Step 4 — services and availability
    service_ids = fields.Many2many("faizy.service", string="Services")
    availability = fields.Text(help="Days and hours the applicant can work.")
    has_vehicle = fields.Boolean()
    vehicle_type = fields.Char()

    # Step 5 — experience and references
    experience_years = fields.Integer()
    experience_notes = fields.Text()
    reference_contacts = fields.Text(help="Name, relationship and phone for each.")

    # Step 6 — documents
    cnic_front = fields.Image(max_width=1920, max_height=1920)
    cnic_back = fields.Image(max_width=1920, max_height=1920)
    selfie = fields.Image(max_width=1920, max_height=1920)

    # Step 7 — agreements
    code_of_conduct_accepted = fields.Boolean()
    rate_card_accepted = fields.Boolean()
    date_accepted = fields.Datetime(readonly=True)

    # Pipeline
    state = fields.Selection(
        [
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("interview", "Interview"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="submitted",
        required=True,
        tracking=True,
        index=True,
        group_expand="_group_expand_state",
    )
    review_notes = fields.Text()
    reviewer_id = fields.Many2one("res.users", string="Reviewed By", readonly=True)
    date_reviewed = fields.Datetime(readonly=True)
    worker_id = fields.Many2one(
        "faizy.worker", string="Faizy", readonly=True, copy=False
    )

    _sql_reference_unique = models.Constraint(
        "unique(reference)", "Application references must be unique."
    )

    @api.model
    def _group_expand_state(self, states, domain):
        return [key for key, _label in self._fields["state"].selection]

    def action_review(self):
        self.write({"state": "under_review"})

    def action_interview(self):
        self.write({"state": "interview"})

    def action_reject(self):
        self.write(
            {
                "state": "rejected",
                "reviewer_id": self.env.user.id,
                "date_reviewed": fields.Datetime.now(),
            }
        )

    def action_approve(self):
        """Promote to an active Faizy. Idempotent — approving twice is a no-op."""
        for application in self:
            if application.worker_id:
                continue
            if not application.code_of_conduct_accepted or not application.rate_card_accepted:
                raise UserError(
                    self.env._(
                        "%(ref)s cannot be approved: the applicant has not accepted "
                        "the code of conduct and rate card.",
                        ref=application.reference,
                    )
                )

            worker = self.env["faizy.worker"].create(
                {
                    "name": application.name,
                    "phone": application.phone,
                    "email": application.email,
                    "cnic": application.cnic,
                    "city": application.city,
                    "area_ids": [(6, 0, application.area_ids.ids)],
                    "service_ids": [(6, 0, application.service_ids.ids)],
                    "state": "active",
                    "image_128": application.selfie,
                }
            )
            application.write(
                {
                    "state": "approved",
                    "worker_id": worker.id,
                    "reviewer_id": self.env.user.id,
                    "date_reviewed": fields.Datetime.now(),
                }
            )
            application.message_post(
                body=self.env._(
                    "Approved. Faizy record %(name)s created.", name=worker.reference
                )
            )

    def action_view_worker(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "faizy.worker",
            "res_id": self.worker_id.id,
            "view_mode": "form",
        }

    @api.depends("reference", "name")
    def _compute_display_name(self):
        for application in self:
            application.display_name = f"{application.reference} — {application.name}"
