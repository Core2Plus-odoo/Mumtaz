from odoo.tests import TransactionCase

# Stage names the module matches on. Kept here so a rename in the module shows
# up as a test failure rather than silently passing against stale fixtures.
PORTFOLIO_STAGES = ["Not Started", "In Progress", "Blocked", "Client Review", "Done"]
DELIVERY_STAGES = ["Backlog", "To Do", "In Progress", "Waiting on Client",
                   "Review", "Done"]


class C2pTrackerCommon(TransactionCase):
    """A two-company portfolio/delivery pair, mirroring the live structure.

    Stages are created per project, as they are in production — each project
    owns its own project.task.type records — so the tests exercise the
    name-based stage resolution rather than a shared set.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_consult = cls.env["res.company"].create({
            "name": "T-Consultants", "currency_id": cls.env.ref("base.AED").id,
        })
        cls.company_solutions = cls.env["res.company"].create({
            "name": "T-Solutions", "parent_id": cls.company_consult.id,
            "currency_id": cls.env.ref("base.AED").id,
        })
        cls.client_partner = cls.env["res.partner"].create({
            "name": "T-Client", "is_company": True,
        })

        Project = cls.env["project.project"]
        cls.portfolio = Project.create({
            "name": "T-Client – Milestones",
            "company_id": cls.company_consult.id,
            "partner_id": cls.client_partner.id,
            "c2p_layer": "portfolio",
            "allow_milestones": True,
        })
        cls.delivery = Project.create({
            "name": "T-Client – Delivery",
            "company_id": cls.company_solutions.id,
            "partner_id": cls.client_partner.id,
            "c2p_layer": "delivery",
            "allow_milestones": True,
        })
        cls.portfolio.c2p_counterpart_id = cls.delivery

        cls.p_stage = cls._make_stages(cls.portfolio, PORTFOLIO_STAGES)
        cls.d_stage = cls._make_stages(cls.delivery, DELIVERY_STAGES)

        # One milestone pair, matched by code, as post_init would wire it.
        cls.dm1 = cls.env["project.milestone"].create({
            "name": "M1 First milestone", "project_id": cls.delivery.id,
        })
        cls.pm1 = cls.env["project.task"].create({
            "name": "M1 First milestone", "project_id": cls.portfolio.id,
            "stage_id": cls.p_stage["Not Started"].id,
            "delivery_milestone_id": cls.dm1.id,
        })

        # NOTE: res.users.group_ids is the Odoo 19 name (groups_id in <=17).
        # If the install reports an unknown field here, that rename is the
        # cause — check with: inspect_odoo_db.py <DB> --schema res.users
        cls.worker = cls.env["res.users"].create({
            "name": "T-Worker", "login": "t-worker",
            "company_id": cls.company_solutions.id,
            "company_ids": [(6, 0, [cls.company_solutions.id])],
            "group_ids": [(4, cls.env.ref(
                "c2p_project_tracker.group_c2p_delivery_member").id)],
        })

    @classmethod
    def _make_stages(cls, project, names):
        """Per-project stages, in order, with Done folded."""
        stages = {}
        for seq, name in enumerate(names, start=1):
            stages[name] = cls.env["project.task.type"].create({
                "name": name, "sequence": seq,
                "fold": name == "Done",
                "project_ids": [(6, 0, [project.id])],
            })
        return stages

    def _delivery_task(self, name="Work", stage="Backlog", **vals):
        """A delivery task. Anything past Backlog needs the hygiene trio, so
        they are supplied by default to keep the tests about one thing each."""
        payload = {
            "name": name, "project_id": self.delivery.id,
            "stage_id": self.d_stage[stage].id,
            "milestone_id": self.dm1.id,
        }
        if stage != "Backlog":
            payload.setdefault("user_ids", [(6, 0, [self.worker.id])])
            payload.setdefault("date_deadline", "2026-12-01")
        payload.update(vals)
        return self.env["project.task"].create(payload)

    def _pm1_stage(self):
        self.pm1.invalidate_recordset()
        return self.pm1.stage_id.name
