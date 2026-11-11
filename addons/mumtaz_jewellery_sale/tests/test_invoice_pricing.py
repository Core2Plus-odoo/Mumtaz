"""The agreed price, and the evidence for it, reach the invoice and stop there.

Standard Odoo already carries `price_unit` from the sale line, so the money
arrives without any help. These tests are about the two things that do not:
the derivation of that money, and the fact that nothing may rewrite it once
the invoice is posted.
"""
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged




def _put_in_stock(env, lot):
    """One unit of the piece on the shelf. Since Slice 1 a piece that is not
    in stock cannot be confirmed, so every fixture that will be sold needs it."""
    stock = env['stock.warehouse'].search(
        [('company_id', '=', env.company.id)], limit=1).lot_stock_id
    env['stock.quant'].with_context(inventory_mode=True).create({
        'product_id': lot.product_id.id, 'lot_id': lot.id,
        'location_id': stock.id, 'inventory_quantity': 1.0,
    }).action_apply_inventory()
    return lot


@tagged('post_install', '-at_install')
class TestInvoicePricing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'mumtaz_jewellery.vat_rate', '5')

        group_mgr = cls.env.ref('mumtaz_jewellery.group_jewellery_manager')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        cls.maker = Users.create({
            'name': 'TEST Inv Maker', 'login': 'test_inv_maker',
            field: [(6, 0, [group_mgr.id])]})
        cls.checker = Users.create({
            'name': 'TEST Inv Checker', 'login': 'test_inv_checker',
            field: [(6, 0, [group_mgr.id])]})

        cls.product = cls.env['product.product'].create({
            'name': 'TEST 22K invoice bangle',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'serial',
            'invoice_policy': 'order',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'TEST Invoice Client'})

    # ---- helpers --------------------------------------------------------
    def _approve_rate(self, value):
        rate = self.env['jewellery.gold.rate'].with_user(self.maker).create({
            'rate_per_gram': value,
            'effective_at': fields.Datetime.now(),
        })
        rate.with_user(self.checker).action_approve()
        return rate

    def _piece(self, seq):
        return _put_in_stock(self.env, self.env['stock.lot'].create({
            'name': 'TEST-INV-%s' % seq,
            'product_id': self.product.id,
            'gross_weight_g': 24.5,
            'stone_weight_g': 0.0,
            'karat': '22',
            'wastage_pct': 2.0,
            'making_type': 'percent',
            'making_value': 10.0,
            'stones_value': 0.0,
        }))

    def _confirmed_order(self, seq, discount=0.0):
        """An order priced from the approved rate and confirmed."""
        lot = self._piece(seq)
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'jewellery_lot_id': lot.id,
                'jewellery_making_discount_pct': discount,
            })],
        })
        # A dealer discount above the staff ceiling needs a manager (Slice 3).
        order.order_line[0].with_user(self.maker).action_price_from_rate()
        order.action_confirm()
        return order, order.order_line[0], lot

    def _invoice(self, order):
        invoice = order._create_invoices()
        self.assertEqual(invoice.state, 'draft')
        return invoice

    def _jewellery_line(self, invoice):
        lines = invoice.invoice_line_ids.filtered('jewellery_lot_id')
        self.assertEqual(len(lines), 1, 'expected one jewellery invoice line')
        return lines

    # ---- the evidence travels -------------------------------------------
    def test_the_whole_breakdown_reaches_the_invoice(self):
        self._approve_rate(245.80)
        _order, so_line, lot = self._confirmed_order(1)
        invoice = self._invoice(_order)
        line = self._jewellery_line(invoice)

        self.assertEqual(line.jewellery_lot_id, lot)
        self.assertEqual(line.jewellery_rate_id, so_line.jewellery_rate_id)
        self.assertAlmostEqual(line.price_unit, so_line.price_unit, 2)
        for name in ('jewellery_rate_per_gram', 'jewellery_fine_weight_g',
                     'jewellery_metal_value', 'jewellery_wastage_value',
                     'jewellery_making_charge', 'jewellery_stones_value'):
            self.assertAlmostEqual(
                line[name], so_line[name], 2,
                msg='%s did not reach the invoice line' % name)
        self.assertEqual(line.jewellery_priced_on, so_line.jewellery_priced_on)
        self.assertTrue(line.jewellery_is_priced)

    def test_the_components_still_add_up_on_the_invoice(self):
        """The evidence has to reconcile with the figure it explains."""
        self._approve_rate(245.80)
        order, _so_line, _lot = self._confirmed_order(2)
        line = self._jewellery_line(self._invoice(order))

        parts = (line.jewellery_metal_value + line.jewellery_wastage_value
                 + line.jewellery_making_charge + line.jewellery_stones_value)
        self.assertAlmostEqual(parts, line.price_unit, 2)

    def test_the_discount_reaches_the_invoice_on_making_only(self):
        self._approve_rate(245.80)
        full_order, _l1, _p1 = self._confirmed_order(3)
        disc_order, _l2, _p2 = self._confirmed_order(4, discount=50.0)
        full = self._jewellery_line(self._invoice(full_order))
        disc = self._jewellery_line(self._invoice(disc_order))

        self.assertAlmostEqual(
            disc.jewellery_metal_value, full.jewellery_metal_value, 2,
            msg='the metal is never discounted')
        self.assertAlmostEqual(
            disc.jewellery_making_charge,
            full.jewellery_making_charge / 2, 2)
        self.assertEqual(disc.jewellery_making_discount_pct, 50.0)

    # ---- THE acceptance test, one document further ----------------------
    def test_posted_invoice_survives_a_rate_change(self):
        """Gold moves daily. A posted invoice must not."""
        self._approve_rate(245.80)
        order, _so_line, _lot = self._confirmed_order(5)
        invoice = self._invoice(order)
        line = self._jewellery_line(invoice)
        invoiced_price = line.price_unit
        invoiced_metal = line.jewellery_metal_value
        invoiced_rate = line.jewellery_rate_per_gram
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

        # the market moves 20% overnight
        self._approve_rate(295.00)
        line.invalidate_recordset()

        self.assertEqual(line.price_unit, invoiced_price)
        self.assertEqual(line.jewellery_metal_value, invoiced_metal)
        self.assertEqual(line.jewellery_rate_per_gram, invoiced_rate)
        self.assertNotEqual(line.jewellery_rate_per_gram, 295.00)

    # ---- the freeze ------------------------------------------------------
    def test_posted_line_refuses_a_price_rewrite(self):
        """Odoo itself permits this without a fiscal lock date or hashing.

        account.move.line.write blocks a posted line only through the fiscal
        lock date, the tax lock date or an inalterable hash. A fresh database
        has none of the three, so without this module the price on a posted
        jewellery invoice can simply be overwritten.
        """
        self._approve_rate(245.80)
        order, _so_line, _lot = self._confirmed_order(6)
        invoice = self._invoice(order)
        invoice.action_post()
        line = self._jewellery_line(invoice)
        with self.assertRaisesRegex(UserError, 'cannot be changed'):
            line.write({'price_unit': 1.0})

    def test_posted_line_refuses_a_snapshot_rewrite(self):
        self._approve_rate(245.80)
        order, _so_line, _lot = self._confirmed_order(7)
        invoice = self._invoice(order)
        invoice.action_post()
        line = self._jewellery_line(invoice)
        with self.assertRaisesRegex(UserError, 'cannot be changed'):
            line.write({'jewellery_rate_per_gram': 1.0})

    def test_the_freeze_holds_for_sudo(self):
        """A correction script or a rate feed must not restate an invoice."""
        self._approve_rate(245.80)
        order, _so_line, _lot = self._confirmed_order(8)
        invoice = self._invoice(order)
        invoice.action_post()
        line = self._jewellery_line(invoice)
        with self.assertRaisesRegex(UserError, 'cannot be changed'):
            line.sudo().write({'jewellery_metal_value': 0.0})

    def test_a_draft_invoice_is_still_editable(self):
        """The freeze starts at posting, not at creation."""
        self._approve_rate(245.80)
        order, _so_line, _lot = self._confirmed_order(9)
        invoice = self._invoice(order)
        line = self._jewellery_line(invoice)
        line.write({'jewellery_metal_value': 123.0})
        self.assertAlmostEqual(line.jewellery_metal_value, 123.0, 2)

    # ---- posting refusals ------------------------------------------------
    def test_posting_an_unpriced_piece_is_refused(self):
        """A hand-made invoice line with a piece and no rate cannot post."""
        self._approve_rate(245.80)
        lot = self._piece(10)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.0,
                'jewellery_lot_id': lot.id,
            })],
        })
        line = self._jewellery_line(invoice)
        self.assertFalse(line.jewellery_is_priced)
        with self.assertRaises(ValidationError):
            invoice.action_post()
        self.assertEqual(invoice.state, 'draft')

    def test_an_ordinary_invoice_posts_untouched(self):
        """Nothing here may break invoicing something that is not jewellery."""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertAlmostEqual(invoice.invoice_line_ids[0].price_unit, 100.0, 2)

    # ---- a credit note is the reason the snapshot is copied --------------
    def test_a_credit_note_carries_the_snapshot_and_posts(self):
        """The case that decided `copy=True` on the invoice-line snapshot.

        A credit note is produced by reversing the move. Had the snapshot been
        copy=False, as it is on the sale line, the reversal would arrive with
        no rate, the posting guard would refuse it, and crediting a jewellery
        invoice would be impossible.
        """
        self._approve_rate(245.80)
        order, _so_line, lot = self._confirmed_order(11)
        invoice = self._invoice(order)
        invoice.action_post()
        original = self._jewellery_line(invoice)
        original_rate = original.jewellery_rate_per_gram
        original_price = original.price_unit

        reversal = invoice._reverse_moves()
        credit_line = self._jewellery_line(reversal)

        self.assertEqual(reversal.move_type, 'out_refund')
        self.assertEqual(credit_line.jewellery_lot_id, lot)
        self.assertEqual(credit_line.jewellery_rate_per_gram, original_rate)
        self.assertAlmostEqual(credit_line.price_unit, original_price, 2)
        self.assertTrue(credit_line.jewellery_is_priced)

        reversal.action_post()
        self.assertEqual(reversal.state, 'posted')
