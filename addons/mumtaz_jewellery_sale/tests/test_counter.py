"""The counter: one call agrees the piece, invoices it, takes the money and
hands it over -- or nothing happens at all. Plus the two counter rules: a
staff discount has a ceiling, and old gold is credited once, from a confirmed
intake, for exactly its engine value.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_sale_commitment import TestSaleCommitment


@tagged('post_install', '-at_install')
class TestCounter(TestSaleCommitment):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'mumtaz_jewellery.staff_discount_limit_pct', '10')
        cls.env['ir.config_parameter'].sudo().set_param(
            'mumtaz_jewellery.exchange_approval_threshold', '0')
        g_sales = cls.env.ref('sales_team.group_sale_salesman')
        field = 'group_ids' if 'group_ids' in cls.staff._fields else 'groups_id'
        cls.staff.write({field: [(4, g_sales.id)]})
        cls.maker.write({field: [(4, g_sales.id)]})
        cls.journal = cls.env['account.journal'].search(
            [('type', 'in', ('cash', 'bank')), ('company_id', '=', cls.company.id)], limit=1)

    # ---- discount ceiling --------------------------------------------------
    def _quote_as(self, user, lot, discount):
        order = self.env['sale.order'].with_user(user).create({
            'partner_id': self.client_a.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1,
                                   'jewellery_lot_id': lot.id,
                                   'jewellery_making_discount_pct': discount})],
        })
        return order

    def test_staff_discount_has_a_ceiling_managers_do_not(self):
        self._approve_rate(245.80)
        ok = self._quote_as(self.staff, self._piece(21), 10.0)
        ok.order_line.with_user(self.staff).action_price_from_rate()     # at the limit: fine
        too_much = self._quote_as(self.staff, self._piece(22), 15.0)
        with self.assertRaises(UserError) as caught:
            too_much.order_line.with_user(self.staff).action_price_from_rate()
        self.assertIn('manager', str(caught.exception).lower())
        mgr = self._quote_as(self.maker, self._piece(23), 15.0)
        mgr.order_line.with_user(self.maker).action_price_from_rate()
        self.assertTrue(mgr.order_line.jewellery_is_priced)

    # ---- old gold credit ---------------------------------------------------
    def _intake(self, partner, grams=18.4, confirm=True):
        intake = self.env['jewellery.old.gold'].with_user(self.maker).create({
            'partner_id': partner.id, 'gross_weight_g': grams, 'karat': '21',
            'melt_loss_pct': 2.0, 'buyback_discount_pct': 5.0})
        if confirm:
            intake.with_user(self.maker).action_confirm()
        return intake

    def test_old_gold_credit_is_the_intake_value_once(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(24))
        total_before = order.amount_total
        intake = self._intake(self.client_a)
        self.assertEqual(intake.state, 'confirmed')
        self.assertGreater(intake.value, 0)

        order.action_apply_old_gold(intake)
        credit = order.order_line.filtered(lambda l: l.price_unit < 0)
        self.assertEqual(len(credit), 1)
        self.assertAlmostEqual(credit.price_unit, -intake.value, 2)
        self.assertAlmostEqual(order.amount_total, total_before - intake.value, 2)
        self.assertEqual(intake.sale_order_id, order)

        with self.assertRaises(UserError):                 # same order, twice
            order.action_apply_old_gold(intake)
        other = self._quote(self.client_a, self._piece(25))
        with self.assertRaises(UserError):                 # another order, same intake
            other.action_apply_old_gold(intake)

    def test_only_a_confirmed_intake_of_this_client_can_be_credited(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(26))
        with self.assertRaises(UserError):
            order.action_apply_old_gold(self._intake(self.client_a, confirm=False))
        with self.assertRaises(UserError):
            order.action_apply_old_gold(self._intake(self.client_b))

    # ---- the commit --------------------------------------------------------
    def test_commit_agrees_invoices_pays_and_delivers_in_one_call(self):
        self._approve_rate(245.80)
        lot = self._piece(27)
        self.assertEqual(lot.product_qty, 1.0)
        order = self._quote(self.client_a, lot)
        out = order.action_counter_commit(journal=self.journal)

        self.assertEqual(order.state, 'sale')
        self.assertEqual(out['invoice'].state, 'posted')
        self.assertIn(out['invoice'].payment_state, ('paid', 'in_payment'))
        self.assertEqual(len(out['payments']), 1)
        self.assertAlmostEqual(out['payments'].amount, out['invoice'].amount_total, 2)
        self.assertTrue(out['pickings'])
        self.assertTrue(all(p.state == 'done' for p in out['pickings']))
        self.assertEqual(lot.product_qty, 0.0, 'the piece has left the shelf')

        # and it cannot be sold again, by either path
        again = self._quote(self.client_b, lot)
        with self.assertRaises(ValidationError):
            again.action_confirm()

    def test_commit_delivers_the_ordered_piece_not_a_sibling(self):
        """Two bangles of the same design on the shelf; the client bought B.
        Standard reservation would hand over whichever serial it picked
        first. The counter hands over B, and A is still on the shelf."""
        self._approve_rate(245.80)
        lot_a = self._piece(31)
        lot_b = self._piece(32)
        order = self._quote(self.client_a, lot_b)
        out = order.action_counter_commit(journal=self.journal)
        delivered = out['pickings'].move_line_ids.mapped('lot_id')
        self.assertEqual(delivered, lot_b)
        self.assertEqual(lot_b.product_qty, 0.0)
        self.assertEqual(lot_a.product_qty, 1.0)

    def test_commit_with_a_deposit_leaves_the_rest_outstanding(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(28))
        out = order.action_counter_commit(journal=self.journal, amount=1000.0)
        self.assertEqual(out['invoice'].payment_state, 'partial')
        self.assertAlmostEqual(out['invoice'].amount_residual, out['invoice'].amount_total - 1000.0, 2)
        self.assertTrue(all(p.state == 'done' for p in out['pickings']))

    def test_commit_with_old_gold_charges_the_difference(self):
        self._approve_rate(245.80)
        order = self._quote(self.client_a, self._piece(29))
        intake = self._intake(self.client_a)
        order.action_apply_old_gold(intake)
        out = order.action_counter_commit(journal=self.journal)
        self.assertAlmostEqual(out['payments'].amount, out['invoice'].amount_total, 2)
        self.assertLess(out['invoice'].amount_total, out['invoice'].amount_untaxed + 1e9)
        credit_line = out['invoice'].invoice_line_ids.filtered(lambda l: l.price_unit < 0)
        self.assertEqual(len(credit_line), 1)

    def test_a_refused_commit_leaves_nothing_behind(self):
        self._approve_rate(245.80)
        lot = self._piece(30)
        order = self._quote(self.client_a, lot)
        Invoice = self.env['account.move']
        Payment = self.env['account.payment']
        invoices_before = Invoice.search_count([('move_type', '=', 'out_invoice')])
        payments_before = Payment.search_count([])
        with self.assertRaises(UserError), self.cr.savepoint():
            order.action_counter_commit(journal=self.journal, amount=10 ** 9)  # more than the total
        self.assertEqual(order.state, 'draft')
        self.assertEqual(Invoice.search_count([('move_type', '=', 'out_invoice')]), invoices_before)
        self.assertEqual(Payment.search_count([]), payments_before)
        self.assertEqual(lot.product_qty, 1.0)
        self.assertFalse(order.picking_ids.filtered(lambda p: p.state == 'done'))
