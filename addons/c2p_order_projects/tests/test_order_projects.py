from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

PARAM = "c2p.order_projects."


@tagged("post_install", "-at_install", "c2p_order_projects")
class TestOrderProjects(TransactionCase):
    """All data is fictional."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env.ref("base.group_user").write({"implied_ids": [
            (4, env.ref("project.group_project_task_dependencies").id)]})
        cls.con = env.company
        cls.sol = env["res.company"].create({"name": "Test Solutions Co"})
        env.user.company_ids |= cls.sol
        cls.partner = env["res.partner"].create(
            {"name": "Test Client Ltd", "is_company": True})
        cls.tpl_con = cls._template("Test oversight template", cls.con, ["To Do", "Done"], tasks=0)
        cls.tpl_sol = cls._template(
            "Test delivery template", cls.sol,
            ["Backlog", "To Do", "In Progress", "Done"], tasks=2, gates=2)
        cls.tpl_sol_no_backlog = cls._template(
            "Test delivery template without backlog", cls.sol,
            ["1. Discovery", "2. Build"], tasks=1)
        cls.product = cls._product("Test project product", cls.tpl_con)
        cls.other_product = cls._product("Test second project product", cls._template(
            "Test second oversight template", cls.con, ["To Do", "Done"], tasks=0))
        cls.delivery_linked_product = cls._product(
            "Test product wrongly linking the delivery template", cls.tpl_sol)
        cls.plain_product = env["product.product"].create(
            {"name": "Test plain service", "type": "service",
             "service_tracking": "no", "list_price": 10})
        cls._configure(enabled="1", company=cls.sol.id, template=cls.tpl_sol.id)

    @classmethod
    def _template(cls, name, company, stages, tasks=0, gates=0):
        project = cls.env["project.project"].create({
            "name": name, "is_template": True, "company_id": company.id,
            "allow_task_dependencies": True, "allow_milestones": True})
        stage_records = [cls.env["project.task.type"].create({
            "name": stage, "sequence": i, "project_ids": [(4, project.id)],
            "fold": stage == "Done"}) for i, stage in enumerate(stages)]
        milestones = [cls.env["project.milestone"].create(
            {"name": "G%d" % (i + 1), "project_id": project.id}) for i in range(gates)]
        previous = cls.env["project.task"]
        for i in range(tasks):
            task = cls.env["project.task"].create({
                "name": "Task %d" % (i + 1), "project_id": project.id,
                "stage_id": stage_records[0].id,
                "milestone_id": milestones[min(i, len(milestones) - 1)].id if milestones else False,
                "depend_on_ids": [(6, 0, previous.ids)]})
            previous = task
        return project

    @classmethod
    def _product(cls, name, oversight_template):
        product = cls.env["product.product"].create({
            "name": name, "type": "service", "service_tracking": "project_only",
            "list_price": 100})
        product.product_tmpl_id.with_company(cls.con).project_template_id = oversight_template
        return product

    @classmethod
    def _configure(cls, enabled=None, company=None, template=None, pair=None):
        icp = cls.env["ir.config_parameter"]
        for key, value in (("enabled", enabled), ("delivery_company_id", company),
                           ("default_delivery_template_id", template),
                           ("pair_in_tracker", pair)):
            if value is not None:
                icp.set_param(PARAM + key, str(value))

    def _order(self, products=None, partner=None, confirm=True, company=None):
        products = products or self.product
        order = self.env["sale.order"].with_company(company or self.con).create({
            "partner_id": (partner or self.partner).id,
            "company_id": (company or self.con).id,
            "order_line": [(0, 0, {"product_id": p.id, "product_uom_qty": 1})
                           for p in products]})
        if confirm:
            order.action_confirm()
        return order

    def _keyed(self, order, **extra):
        return self.env["project.project"].with_context(active_test=False).search(
            [("c2p_source_order_id", "=", order.id)] + list(extra.get("domain", [])))

    def _role(self, order, role):
        return self._keyed(order).filtered(lambda p: p.c2p_project_role == role)

    # ── The pair ─────────────────────────────────────────────────────────
    def test_switched_off_creates_nothing(self):
        self._configure(enabled="0")
        order = self._order()
        self.assertFalse(self._keyed(order))

    def test_new_order_creates_the_pair(self):
        order = self._order()
        oversight, delivery = self._role(order, "oversight"), self._role(order, "delivery")
        self.assertEqual(len(oversight), 1)
        self.assertEqual(len(delivery), 1)
        self.assertEqual(oversight.company_id, self.con)
        self.assertEqual(delivery.company_id, self.sol)
        self.assertEqual(delivery.partner_id, self.partner)
        self.assertEqual(oversight.partner_id, self.partner)
        self.assertFalse(delivery.is_template)
        self.assertEqual(delivery.name, "%s – Delivery" % oversight.name)
        self.assertEqual(len(delivery.task_ids), 2)
        self.assertEqual(sum(len(t.depend_on_ids) for t in delivery.task_ids), 1)
        self.assertEqual(delivery.milestone_ids.mapped("name"), ["G1", "G2"])
        self.assertEqual(oversight.c2p_layer, "portfolio")
        self.assertEqual(delivery.c2p_layer, "delivery")
        self.assertEqual(oversight.c2p_counterpart_id, delivery)
        self.assertEqual(delivery.c2p_counterpart_id, oversight)
        self.assertTrue(any("Delivery project created" in (m.body or "")
                            for m in oversight.message_ids))

    def test_any_project_product_qualifies_without_a_proposal(self):
        order = self._order()
        self.assertEqual(len(self._keyed(order)), 2)

    def test_order_without_a_project_product_creates_nothing(self):
        order = self._order(self.plain_product)
        self.assertFalse(self._keyed(order))

    def test_two_orders_give_two_pairs(self):
        first, second = self._order(), self._order()
        self.assertEqual(len(self._keyed(first)), 2)
        self.assertEqual(len(self._keyed(second)), 2)
        self.assertFalse(self._keyed(first) & self._keyed(second))

    # ── Repeats ──────────────────────────────────────────────────────────
    def test_ensure_is_idempotent(self):
        order = self._order()
        before = self._keyed(order)
        order._c2p_ensure_project_pair()
        order._c2p_ensure_project_pair()
        self.assertEqual(self._keyed(order), before)

    def test_confirming_again_is_refused_and_creates_nothing(self):
        order = self._order()
        before = self._keyed(order)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(self._keyed(order), before)

    def test_cancel_reset_and_confirm_again_creates_nothing(self):
        order = self._order()
        before = self._keyed(order)
        order._action_cancel()
        order.action_draft()
        order.action_confirm()
        self.assertEqual(self._keyed(order), before)

    # ── Archived and templates ───────────────────────────────────────────
    def test_archived_delivery_project_blocks_a_replacement(self):
        order = self._order()
        delivery = self._role(order, "delivery")
        delivery.active = False
        order._c2p_ensure_project_pair()
        self.assertEqual(self._role(order, "delivery"), delivery)
        self.assertEqual(len(self._keyed(order)), 2)

    def test_archived_oversight_project_blocks_a_replacement(self):
        order = self._order()
        oversight = self._role(order, "oversight")
        oversight.active = False
        order._c2p_ensure_project_pair()
        self.assertEqual(self._role(order, "oversight"), oversight)
        self.assertEqual(len(self._keyed(order)), 2)

    def test_a_template_with_the_order_link_is_ignored(self):
        order = self._order(confirm=False)
        template = self.env["project.project"].create({
            "name": "Template carrying a key", "is_template": True,
            "c2p_source_order_id": order.id, "c2p_project_role": "delivery"})
        order.action_confirm()
        delivery = self._role(order, "delivery").filtered(lambda p: not p.is_template)
        self.assertEqual(len(delivery), 1)
        self.assertNotEqual(delivery, template)

    # ── The key ──────────────────────────────────────────────────────────
    @mute_logger("odoo.sql_db")
    def test_index_refuses_a_second_project_with_the_same_key(self):
        order = self._order()
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["project.project"].create({
                "name": "Duplicate", "c2p_source_order_id": order.id,
                "c2p_project_role": "delivery"})

    @mute_logger("odoo.sql_db")
    def test_index_counts_archived_projects(self):
        order = self._order()
        self._role(order, "delivery").active = False
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["project.project"].create({
                "name": "Duplicate of an archived one", "c2p_source_order_id": order.id,
                "c2p_project_role": "delivery"})

    @mute_logger("odoo.sql_db")
    def test_losing_a_race_returns_the_existing_project(self):
        order = self._order()
        delivery = self._role(order, "delivery")
        oversight = self._role(order, "oversight")
        result = order._c2p_create_delivery(
            oversight, order._c2p_project_lines(), order._c2p_settings())
        self.assertEqual(result, delivery)
        self.assertEqual(len(self._keyed(order)), 2)

    # ── Settings and failures ────────────────────────────────────────────
    def test_missing_template_does_not_block_the_confirmation(self):
        self._configure(template=999999)
        order = self._order()
        self.assertEqual(order.state, "sale")
        self.assertFalse(self._role(order, "delivery"))
        self.assertTrue(any("No delivery project was created" in (m.body or "")
                            for m in order.message_ids))

    def test_delivery_company_equal_to_order_company_is_skipped(self):
        self._configure(company=self.con.id)
        order = self._order()
        self.assertFalse(self._role(order, "delivery"))

    def test_an_error_does_not_block_the_confirmation(self):
        with patch.object(type(self.env["sale.order"]), "_c2p_create_delivery",
                          side_effect=ValueError("boom")), mute_logger(
                "odoo.addons.c2p_order_projects.models.sale_order"):
            order = self._order()
        self.assertEqual(order.state, "sale")
        self.assertFalse(self._role(order, "delivery"))
        self.assertTrue(any("Automatic project set-up failed" in (m.body or "")
                            for m in order.message_ids))

    def test_product_template_overrides_the_default(self):
        override = self._template(
            "Override delivery template", self.sol, ["Backlog", "Done"], tasks=3)
        self.product.product_tmpl_id.c2p_delivery_template_id = override
        order = self._order()
        self.assertEqual(len(self._role(order, "delivery").task_ids), 3)

    # ── Tracker pairing ──────────────────────────────────────────────────
    def test_pairing_can_be_switched_off(self):
        self._configure(pair=0)
        order = self._order()
        self.assertFalse(self._role(order, "oversight").c2p_layer)
        self.assertFalse(self._role(order, "oversight").c2p_counterpart_id)

    def test_template_without_backlog_stage_is_left_unpaired(self):
        self._configure(template=self.tpl_sol_no_backlog.id)
        order = self._order()
        delivery = self._role(order, "delivery")
        self.assertEqual(len(delivery), 1)
        self.assertFalse(delivery.c2p_layer)
        self.assertFalse(self._role(order, "oversight").c2p_counterpart_id)
        self.assertTrue(any("not paired" in (m.body or "")
                            for m in order.message_ids))

    # ── Several products ─────────────────────────────────────────────────
    def test_two_project_lines_give_no_delivery_project(self):
        order = self._order(self.product | self.other_product)
        self.assertEqual(len(self._role(order, "oversight")), 1)
        self.assertFalse(self._role(order, "delivery"))
        self.assertEqual(len(self._keyed(order)), 1)
        self.assertTrue(any("more than one project line" in (m.body or "")
                            for m in order.message_ids))

    def test_the_note_names_the_extra_project(self):
        order = self._order(self.product | self.other_product)
        extra = order.order_line.sudo().project_id - self._role(order, "oversight")
        note = next(m.body for m in order.message_ids if "more than one project line" in (m.body or ""))
        self.assertTrue(extra)
        self.assertIn(extra.name, note)

    def test_an_archived_extra_project_still_blocks_the_delivery_project(self):
        order = self._order(self.product | self.other_product)
        extra = order.order_line.sudo().project_id - self._role(order, "oversight")
        extra.active = False
        order._c2p_ensure_project_pair()
        self.assertFalse(self._role(order, "delivery"))

    def test_a_delivery_template_linked_as_the_standard_template_blocks_the_delivery_project(self):
        order = self._order(self.delivery_linked_product | self.product)
        self.assertEqual(len(self._role(order, "oversight")), 1)
        self.assertFalse(self._role(order, "delivery"))
        self.assertEqual(len(self._keyed(order)), 1)

    def test_a_delivery_template_as_the_only_standard_link_leaves_the_order_alone(self):
        order = self._order(self.delivery_linked_product)
        self.assertFalse(self._keyed(order))
        self.assertTrue(any("No oversight project exists" in (m.body or "")
                            for m in order.message_ids))

    # ── Access ───────────────────────────────────────────────────────────
    def test_consultants_only_salesperson_can_confirm(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Test salesperson", "login": "test_salesperson_op",
            "company_id": self.con.id, "company_ids": [(6, 0, [self.con.id])],
            "group_ids": [(6, 0, [self.env.ref("sales_team.group_sale_salesman").id])]})
        as_user = self.env["sale.order"].with_user(user).with_context(
            allowed_company_ids=[self.con.id])
        order = as_user.create({
            "partner_id": self.partner.id, "company_id": self.con.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})]})
        order.action_confirm()
        self.assertEqual(len(self._keyed(order)), 2)
        visible = self.env["project.project"].with_user(user).with_context(
            allowed_company_ids=[self.con.id]).search_count(
            [("c2p_source_order_id", "=", order.id), ("company_id", "=", self.sol.id)])
        self.assertEqual(visible, 0)
