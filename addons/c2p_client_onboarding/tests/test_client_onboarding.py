from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from ..models.c2p_onboarding_check import GATE_CHECKS

G = "c2p_project_tracker.group_c2p_%s"


@tagged("post_install", "-at_install")
class TestClientOnboarding(TransactionCase):
    """Synthetic data only: one TEST client, one Consultants engagement and its
    paired Solutions project in a second company."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.consult = env["res.company"].create({"name": "TEST Consultants"})
        cls.solutions = env["res.company"].create({"name": "TEST Solutions"})
        both = [(6, 0, [cls.consult.id, cls.solutions.id])]

        def user(login, group, company, companies):
            return env["res.users"].with_context(no_reset_password=True).create({
                "name": "TEST " + login, "login": login,
                "company_id": company.id, "company_ids": companies,
                "group_ids": [(6, 0, [env.ref("base.group_user").id,
                                      env.ref(group).id])]})

        cls.manager = user("t-owner", G % "portfolio_manager", cls.consult, both)
        cls.lead = user("t-lead", G % "delivery_lead", cls.solutions, both)
        cls.member = user("t-member", G % "delivery_member", cls.solutions,
                          [(6, 0, [cls.solutions.id])])
        cls.outsider = user("t-outsourced", "project.group_project_user",
                            cls.solutions, [(6, 0, [cls.solutions.id])])

        cls.client = env["res.partner"].create({
            "name": "TEST Client LLC", "is_company": True,
            "c2p_is_client": True})
        cls.other_client = env["res.partner"].create({
            "name": "TEST Other Client", "is_company": True,
            "c2p_is_client": True})
        Project = env["project.project"]
        cls.portfolio = Project.create({
            "name": "TEST Client – Engagement", "company_id": cls.consult.id,
            "partner_id": cls.client.id, "c2p_layer": "portfolio",
            "account_manager_id": cls.manager.id})
        cls.delivery = Project.create({
            "name": "TEST Client – Delivery", "company_id": cls.solutions.id,
            "partner_id": cls.client.id, "c2p_layer": "delivery",
            "user_id": cls.lead.id, "privacy_visibility": "followers"})
        cls.portfolio.c2p_counterpart_id = cls.delivery

    # ── helpers ──────────────────────────────────────────────────────────
    def _check(self, code):
        return self.portfolio.c2p_onboarding_check_ids.filtered(
            lambda c: c.code == code)

    def _approve_scope(self):
        self.portfolio.write({
            "c2p_scope_reference": "TEST-SO-001", "c2p_scope_version": "1.0",
            "c2p_scope_summary": "Accounting and sales.",
            "c2p_scope_exclusions": "Payroll."})
        self.portfolio.with_user(self.manager).action_c2p_approve_scope()

    def _complete_everything(self):
        self.client.c2p_legal_name = "TEST Client L.L.C."
        self.env["res.partner"].create({
            "name": "TEST Approver", "parent_id": self.client.id,
            "c2p_contact_role": "approver", "email": "approver@example.com"})
        self._approve_scope()
        self.client.action_c2p_add_standard_documents()
        self.client.c2p_document_ids.filtered(
            lambda d: d.code == "nda").state = "received"
        self.portfolio.action_c2p_start_onboarding_checklist()
        for check in self.portfolio.c2p_onboarding_check_ids:
            check.note = "TEST evidence ref"
            check.action_done()

    # ── no duplicate records ─────────────────────────────────────────────
    def test_no_project_or_partner_is_created(self):
        """The whole journey reuses the existing partner and project pair."""
        projects = self.env["project.project"].search_count([])
        companies = self.env["res.partner"].search_count(
            [("is_company", "=", True)])
        self._complete_everything()
        self.portfolio.with_user(self.manager).action_c2p_confirm_onboarding()
        self.assertEqual(self.env["project.project"].search_count([]), projects)
        self.assertEqual(self.env["res.partner"].search_count(
            [("is_company", "=", True)]), companies)

    def test_client_shows_engagement_and_solutions_project(self):
        self.assertEqual(self.client.c2p_engagement_ids, self.portfolio)
        self.assertEqual(self.portfolio.c2p_counterpart_id, self.delivery)
        self.assertEqual(self.portfolio.c2p_delivery_lead_id, self.lead)

    # ── checklist ────────────────────────────────────────────────────────
    def test_checklist_is_created_once(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        self.portfolio.action_c2p_start_onboarding_checklist()
        self.assertEqual(len(self.portfolio.c2p_onboarding_check_ids),
                         len(GATE_CHECKS))

    @mute_logger("odoo.sql_db")
    def test_duplicate_check_is_refused_by_the_database(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["c2p.onboarding.check"].create({
                "project_id": self.portfolio.id, "code": "scope",
                "name": "again"})
            self.env.flush_all()

    def test_checklist_prefills_owner_due_date_and_blocking(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        self.assertEqual(self._check("scope").owner_id, self.manager)
        self.assertEqual(self._check("solutions_owner").owner_id, self.lead)
        self.assertTrue(all(self.portfolio.c2p_onboarding_check_ids.mapped(
            "due_date")))
        self.assertEqual(self._check("scope").blocks, "kickoff")
        self.assertEqual(self._check("deliverables").blocks, "delivery")

    def test_checklist_only_on_the_engagement(self):
        with self.assertRaises(UserError):
            self.delivery.action_c2p_start_onboarding_checklist()

    def test_check_needs_real_evidence(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        for code in ("legal_entity", "client_contacts", "scope",
                     "confidentiality", "deliverables"):
            with self.subTest(code=code), self.assertRaises(UserError):
                self._check(code).action_done()
        # The pair is linked and managed, so this one is already true.
        self._check("solutions_owner").action_done()
        self.assertEqual(self._check("solutions_owner").state, "done")
        self.assertEqual(self.portfolio.c2p_onboarding_state, "in_progress")

    def test_not_applicable_needs_a_reason(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        check = self._check("payment")
        with self.assertRaises(UserError):
            check.action_not_applicable()
        check.na_reason = "TEST: fixed fee paid in advance"
        check.action_not_applicable()
        self.assertEqual(check.state, "na")

    def test_state_cannot_be_written_directly(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        with self.assertRaises(UserError):
            self._check("scope").write({"state": "done"})

    def test_confirm_needs_every_check_and_a_manager(self):
        self.portfolio.action_c2p_start_onboarding_checklist()
        with self.assertRaises(UserError):
            self.portfolio.with_user(self.manager).action_c2p_confirm_onboarding()
        self._complete_everything()
        self.assertEqual(self.portfolio.c2p_onboarding_state, "ready")
        self.assertEqual(self.client.c2p_onboarding_state, "ready")
        with self.assertRaises(AccessError):
            self.portfolio.with_user(self.lead).action_c2p_confirm_onboarding()
        self.portfolio.with_user(self.manager).action_c2p_confirm_onboarding()
        self.assertEqual(self.portfolio.c2p_onboarding_state, "onboarded")
        self.assertEqual(self.client.c2p_onboarding_state, "onboarded")
        self.assertEqual(self.portfolio.c2p_onboarded_by_id, self.manager)
        # Frozen once confirmed.
        with self.assertRaises(UserError):
            self._check("scope").action_reopen()

    # ── scope ────────────────────────────────────────────────────────────
    def test_scope_approval_rules(self):
        with self.assertRaises(UserError):
            self.portfolio.with_user(self.manager).action_c2p_approve_scope()
        self.portfolio.write({
            "c2p_scope_reference": "TEST-SO-001",
            "c2p_scope_summary": "Accounting.", "c2p_scope_exclusions": "HR."})
        with self.assertRaises(AccessError):
            self.portfolio.with_user(self.lead).action_c2p_approve_scope()
        with self.assertRaises(UserError):
            self.portfolio.write({"c2p_scope_state": "approved"})
        self.portfolio.with_user(self.manager).action_c2p_approve_scope()
        with self.assertRaises(UserError):
            self.portfolio.write({"c2p_scope_summary": "Everything."})
        self.portfolio.with_user(self.manager).action_c2p_reopen_scope()
        self.portfolio.write({"c2p_scope_summary": "Accounting and stock."})

    def test_reopening_scope_reopens_its_check(self):
        self._complete_everything()
        self.portfolio.with_user(self.manager).action_c2p_reopen_scope()
        self.assertEqual(self._check("scope").state, "open")
        self.assertEqual(self.portfolio.c2p_onboarding_state, "in_progress")

    # ── next required action ─────────────────────────────────────────────
    def test_next_action_names_the_kickoff_blocker_first(self):
        self.assertIn("customer on the portfolio project",
                      self.other_client.c2p_next_action)
        self.assertIn("Start the onboarding checklist",
                      self.client.c2p_next_action)
        self.portfolio.action_c2p_start_onboarding_checklist()
        self.client.invalidate_recordset()
        self.assertIn("Correct legal client entity", self.client.c2p_next_action)
        self.assertIn("Blocks kickoff", self.client.c2p_next_action)

    # ── credentials stay out ─────────────────────────────────────────────
    def _access(self, **vals):
        base = {"name": "TEST Odoo production admin",
                "partner_id": self.client.id,
                "holder_id": self.lead.partner_id.id}
        base.update(vals)
        return self.env["c2p.client.access"].create(base)

    def test_vault_reference_format_is_enforced(self):
        self._access(vault_ref="vault://test-clients/test-client/odoo-admin")
        for bad in ("Hunter2!", "https://vault.example.com/x",
                    "vault://only-collection", "vault://a/b c"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self._access(vault_ref=bad)

    def test_text_that_looks_like_a_secret_is_refused(self):
        with self.assertRaises(ValidationError):
            self._access(purpose="password: Hunter2")
        with self.assertRaises(ValidationError):
            self.env["c2p.client.instance"].create({
                "name": "TEST prod", "partner_id": self.client.id,
                "url": "https://admin:Hunter2@test.example.com"})
        with self.assertRaises(ValidationError):
            self.env["c2p.client.document"].create({
                "name": "TEST doc", "partner_id": self.client.id,
                "location": "api_key=abc123"})

    def test_access_model_has_no_secret_or_chatter_field(self):
        fields_ = self.env["c2p.client.access"]._fields
        for name in ("password", "secret", "token", "key", "message_ids",
                     "notes"):
            self.assertNotIn(name, fields_)

    def test_shared_credential_needs_vault_reference_to_grant(self):
        row = self._access(credential_kind="shared")
        with self.assertRaises(UserError):
            row.with_user(self.lead).action_grant()
        row.vault_ref = "vault://test-clients/test-client/odoo-admin"
        row.with_user(self.lead).action_grant()
        self.assertEqual(row.state, "active")
        self.assertEqual(row.granted_by_id, self.lead)
        with self.assertRaises(UserError):
            row.write({"state": "requested"})
        row.with_user(self.lead).action_revoke()
        self.assertEqual(row.revoked_by_id, self.lead)

    def test_access_cannot_point_at_another_clients_instance(self):
        instance = self.env["c2p.client.instance"].create({
            "name": "TEST other prod", "partner_id": self.other_client.id})
        with self.assertRaises(ValidationError):
            self._access(instance_id=instance.id)

    def test_instance_prefills_the_only_solutions_project(self):
        instance = self.env["c2p.client.instance"].create({
            "name": "TEST prod", "partner_id": self.client.id})
        self.assertEqual(instance.project_id, self.delivery)

    def test_standard_documents_are_added_once(self):
        self.client.action_c2p_add_standard_documents()
        count = len(self.client.c2p_document_ids)
        self.client.action_c2p_add_standard_documents()
        self.assertEqual(len(self.client.c2p_document_ids), count)
        with self.assertRaises(ValidationError):
            self.client.c2p_document_ids[0].state = "na"

    # ── who can see what ─────────────────────────────────────────────────
    def test_member_sees_only_own_access_and_cannot_grant(self):
        mine = self._access(holder_id=self.member.partner_id.id,
                            company_id=self.solutions.id)
        theirs = self._access(company_id=self.solutions.id)
        Access = self.env["c2p.client.access"].with_user(self.member)
        self.assertEqual(Access.search([]), mine)
        with self.assertRaises(AccessError):
            theirs.with_user(self.member).read(["vault_ref"])
        with self.assertRaises(AccessError):
            mine.with_user(self.member).action_grant()
        with self.assertRaises(AccessError):
            mine.with_user(self.member).write({"purpose": "x"})
        self.assertEqual(
            self.env["c2p.client.access"].with_user(self.lead).search(
                [("id", "in", (mine | theirs).ids)]), mine | theirs)

    def test_outsourced_contributor_reaches_none_of_it(self):
        """A plain project user with no tracker group: their own task and
        nothing else."""
        self._access(company_id=self.solutions.id)
        self.env["c2p.client.instance"].create({
            "name": "TEST prod", "partner_id": self.client.id})
        self.portfolio.action_c2p_start_onboarding_checklist()
        for model in ("c2p.client.access", "c2p.client.instance",
                      "c2p.client.document", "c2p.onboarding.check"):
            with self.subTest(model=model), self.assertRaises(AccessError):
                self.env[model].with_user(self.outsider).search([])
        with self.assertRaises(AccessError):
            self.client.with_user(self.outsider).read(["c2p_next_action"])

        other = self.env["project.project"].create({
            "name": "TEST Other – Delivery", "company_id": self.solutions.id,
            "partner_id": self.other_client.id, "c2p_layer": "delivery",
            "privacy_visibility": "followers"})
        Task = self.env["project.task"]
        assigned = Task.create({
            "name": "TEST outsourced task", "project_id": self.delivery.id,
            "user_ids": [(6, 0, [self.outsider.id])]})
        Task.create({"name": "TEST unrelated", "project_id": other.id})
        Task.create({"name": "TEST same client, not theirs",
                     "project_id": self.delivery.id})
        # Not invited to the project: only the task they are assigned to.
        visible = Task.with_user(self.outsider).search(
            [("name", "like", "TEST"), ("project_id", "!=", False)])
        self.assertEqual(visible, assigned)
        self.assertFalse(self.env["project.project"].with_user(
            self.outsider).search([("id", "=", other.id)]))

    def test_other_company_rows_are_hidden(self):
        row = self.env["c2p.client.instance"].create({
            "name": "TEST consult-only", "partner_id": self.client.id,
            "company_id": self.consult.id})
        self.assertFalse(self.env["c2p.client.instance"].with_user(
            self.member).search([("id", "=", row.id)]))

    # ── email is a draft ─────────────────────────────────────────────────
    def test_welcome_email_refuses_unverified_data(self):
        with self.assertRaises(UserError):
            self.portfolio.action_c2p_draft_welcome_email()

    def test_welcome_email_opens_a_draft_and_sends_nothing(self):
        self._complete_everything()
        mails = self.env["mail.mail"].search_count([])
        messages = self.env["mail.message"].search_count(
            [("model", "=", "project.project"),
             ("res_id", "=", self.portfolio.id),
             ("message_type", "=", "comment")])
        action = self.portfolio.action_c2p_draft_welcome_email()
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(action["target"], "new")
        self.assertTrue(action["context"]["default_partner_ids"])
        self.assertEqual(self.env["mail.mail"].search_count([]), mails)
        self.assertEqual(self.env["mail.message"].search_count(
            [("model", "=", "project.project"),
             ("res_id", "=", self.portfolio.id),
             ("message_type", "=", "comment")]), messages)

    # ── uploads ──────────────────────────────────────────────────────────
    FILE = "VEVTVCBmaWxlIGNvbnRlbnQ="  # base64 of fictional text

    def _docs(self):
        self.client.action_c2p_add_standard_documents()
        return {d.code: d for d in self.client.c2p_document_ids}

    def test_uploading_a_file_marks_the_document_received(self):
        doc = self._docs()["trade_licence"]
        self.assertEqual(doc.state, "required")
        doc.with_user(self.lead).write(
            {"file": self.FILE, "file_name": "TEST-licence.pdf"})
        self.assertEqual(doc.state, "received")
        self.assertTrue(doc.received_on)
        self.assertEqual(doc.file_name, "TEST-licence.pdf")
        self.assertTrue(doc.file)

    def test_upload_does_not_downgrade_a_verified_document(self):
        doc = self._docs()["contract"]
        doc.state = "verified"
        doc.write({"file": self.FILE, "file_name": "TEST-contract-v2.pdf"})
        self.assertEqual(doc.state, "verified")

    def test_uploaded_file_is_an_attachment_not_a_column(self):
        doc = self._docs()["nda"]
        doc.write({"file": self.FILE, "file_name": "TEST-nda.pdf"})
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "c2p.client.document"),
            ("res_id", "=", doc.id), ("res_field", "=", "file")])
        self.assertEqual(len(attachment), 1)

    def test_member_can_download_but_not_upload(self):
        doc = self._docs()["nda"]
        doc.write({"file": self.FILE, "file_name": "TEST-nda.pdf"})
        as_member = doc.with_user(self.member)
        self.assertTrue(as_member.read(["file"])[0]["file"])
        with self.assertRaises(AccessError):
            as_member.write({"file": self.FILE, "file_name": "TEST-x.pdf"})

    def test_outsourced_contributor_cannot_reach_uploaded_files(self):
        doc = self._docs()["nda"]
        doc.write({"file": self.FILE, "file_name": "TEST-nda.pdf"})
        with self.assertRaises(AccessError):
            doc.with_user(self.outsider).read(["file"])

    def test_scope_file_is_locked_once_scope_is_approved(self):
        self.portfolio.write({
            "c2p_scope_file": self.FILE,
            "c2p_scope_file_name": "TEST-signed-order.pdf"})
        self._approve_scope()
        with self.assertRaises(UserError):
            self.portfolio.write({"c2p_scope_file": self.FILE,
                                  "c2p_scope_file_name": "TEST-other.pdf"})
        self.portfolio.with_user(self.manager).action_c2p_reopen_scope()
        self.portfolio.write({"c2p_scope_file": self.FILE,
                              "c2p_scope_file_name": "TEST-revised.pdf"})
        self.assertEqual(self.portfolio.c2p_scope_file_name,
                         "TEST-revised.pdf")
