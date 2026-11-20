"""A piece out on approval leaves the shelf but stays on the books.

Before this, a memo wrote a state field and nothing else, so metal sitting in
a client's house still counted as on hand: stock value overstated what was
held and a shop count could not reconcile. These tests pin down the fix, and
the thing they most need to prove is that the piece is still *owned* — it
moves to an internal location, never out to a customer.
"""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMemoStock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.shelf = cls.warehouse.lot_stock_id
        cls.approval = cls.env.ref('mumtaz_jewellery_vip.location_on_approval')
        cls.customers = cls.env.ref('stock.stock_location_customers')

        cls.product = cls.env['product.product'].create({
            'name': 'TEST memo bangle',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'serial',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'TEST memo client'})

    # ---- helpers --------------------------------------------------------
    def _piece_on_shelf(self, seq):
        lot = self.env['stock.lot'].create({
            'name': 'TEST-MEMO-%s' % seq,
            'product_id': self.product.id,
            'gross_weight_g': 20.0,
            'karat': '22',
        })
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'lot_id': lot.id,
            'location_id': self.shelf.id,
            'inventory_quantity': 1.0,
        })._apply_inventory()
        return lot

    def _memo(self, lots):
        return self.env['jewellery.approval.memo'].create({
            'partner_id': self.partner.id,
            'lot_ids': [(6, 0, lots.ids)],
            'return_by': fields.Date.add(fields.Date.today(), days=7),
        })

    def _qty_at(self, lot, location):
        quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id), ('location_id', '=', location.id)])
        return sum(quants.mapped('quantity'))

    # ---- the piece leaves the shelf -------------------------------------
    def test_handing_a_piece_over_takes_it_off_the_shelf(self):
        lot = self._piece_on_shelf(1)
        self.assertEqual(self._qty_at(lot, self.shelf), 1.0)

        memo = self._memo(lot)
        memo.action_out()

        self.assertEqual(self._qty_at(lot, self.shelf), 0.0,
                         'the shelf count must drop')
        self.assertEqual(self._qty_at(lot, self.approval), 1.0)

    def test_a_piece_on_approval_is_still_owned(self):
        """The whole modelling decision: internal, never a customer location."""
        lot = self._piece_on_shelf(2)
        memo = self._memo(lot)
        memo.action_out()

        self.assertEqual(self.approval.usage, 'internal',
                         'on approval is still our stock, not a delivery')
        self.assertEqual(self._qty_at(lot, self.customers), 0.0,
                         'it has not been sold')

    # ---- and comes back --------------------------------------------------
    def test_returning_puts_it_back_on_the_shelf(self):
        lot = self._piece_on_shelf(3)
        memo = self._memo(lot)
        memo.action_out()
        memo.action_return()

        self.assertEqual(memo.state, 'returned')
        self.assertEqual(self._qty_at(lot, self.approval), 0.0)
        self.assertEqual(self._qty_at(lot, self.shelf), 1.0)

    def test_selling_sends_it_to_the_customer(self):
        lot = self._piece_on_shelf(4)
        memo = self._memo(lot)
        memo.action_out()
        memo.action_sold()

        self.assertEqual(memo.state, 'sold')
        self.assertEqual(self._qty_at(lot, self.approval), 0.0)
        self.assertEqual(self._qty_at(lot, self.shelf), 0.0)
        self.assertEqual(self._qty_at(lot, self.customers), 1.0)

    # ---- several pieces on one memo -------------------------------------
    def test_a_memo_moves_every_piece_on_it(self):
        lots = self.env['stock.lot']
        for seq in (5, 6, 7):
            lots |= self._piece_on_shelf(seq)
        memo = self._memo(lots)
        memo.action_out()

        for lot in lots:
            self.assertEqual(self._qty_at(lot, self.approval), 1.0)
            self.assertEqual(self._qty_at(lot, self.shelf), 0.0)

    # ---- refusals --------------------------------------------------------
    def test_a_returned_memo_cannot_be_returned_again(self):
        lot = self._piece_on_shelf(8)
        memo = self._memo(lot)
        memo.action_out()
        memo.action_return()
        with self.assertRaisesRegex(UserError, 'nothing to'):
            memo.action_return()

    def test_a_sold_memo_cannot_be_sold_again(self):
        lot = self._piece_on_shelf(9)
        memo = self._memo(lot)
        memo.action_out()
        memo.action_sold()
        with self.assertRaisesRegex(UserError, 'cannot be sold'):
            memo.action_sold()

    def test_a_returned_memo_cannot_then_be_sold(self):
        lot = self._piece_on_shelf(10)
        memo = self._memo(lot)
        memo.action_out()
        memo.action_return()
        with self.assertRaisesRegex(UserError, 'cannot be sold'):
            memo.action_sold()

    # ---- a piece that was never in stock ---------------------------------
    def test_a_piece_not_in_stock_is_skipped_not_fatal(self):
        """A memo may list a piece that was never received. Recording the
        return of the others still has to work."""
        on_shelf = self._piece_on_shelf(11)
        phantom = self.env['stock.lot'].create({
            'name': 'TEST-MEMO-PHANTOM',
            'product_id': self.product.id,
            'gross_weight_g': 20.0,
            'karat': '22',
        })
        memo = self._memo(on_shelf | phantom)
        memo.action_out()

        self.assertEqual(self._qty_at(on_shelf, self.approval), 1.0)
        self.assertEqual(self._qty_at(phantom, self.approval), 0.0)

    # ---- the insured value still works ----------------------------------
    def test_insured_value_survives_the_move(self):
        lot = self._piece_on_shelf(12)
        memo = self._memo(lot)
        before = memo.insured_value
        memo.action_out()
        memo.invalidate_recordset()
        self.assertEqual(memo.insured_value, before)
