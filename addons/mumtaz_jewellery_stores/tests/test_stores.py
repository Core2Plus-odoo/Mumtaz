"""Stores: custody per warehouse, two-sided transfers through standard
stock moves, fine-gram reconciliation with a named variance, store
isolation, and the door."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.mumtaz_jewellery_api.tests.test_api import TestJawharApiSale
from odoo.addons.mumtaz_jewellery_crm.tests.test_tray import TrayCase


def _second_store(env, name='TEST Store 2', code='TS2'):
    W = env['stock.warehouse']
    return W.search([('code', '=', code)], limit=1) or W.create({'name': name, 'code': code, 'company_id': env.company.id})


class StoresCase(TrayCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.store1 = env['stock.warehouse'].search([('company_id', '=', env.company.id)], order='id', limit=1)
        cls.store2 = _second_store(env)
        cls.Transfer = env['jewellery.transfer']
        cls.Recon = env['jewellery.gold.reconciliation']
        cls.staff.jewellery_store_id = cls.store1
        Users = env['res.users'].with_context(no_reset_password=True)
        field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        cls.staff2 = Users.create({'name': 'TEST Store2 Staff', 'login': 'store2_staff', 'jewellery_store_id': cls.store2.id,
                                   field: [(6, 0, [env.ref('mumtaz_jewellery.group_jewellery_user').id])]})

    def fine(self, lots):
        return sum((l.net_weight_g or 0.0) * float(l.karat or 0) / 24.0 for l in lots)

    def transfer(self, lots, user=None, src=None, dst=None):
        return self.Transfer.with_user(user or self.staff).create({
            'from_warehouse_id': (src or self.store1).id, 'to_warehouse_id': (dst or self.store2).id,
            'lot_ids': [(6, 0, [l.id for l in lots])]})


@tagged('post_install', '-at_install')
class TestTransfers(StoresCase):

    def test_a_store_is_a_warehouse_with_pieces_fine_grams_and_value(self):
        s = self.store1.jewellery_summary()
        self.assertEqual(s['pieces'], 6)
        self.assertAlmostEqual(s['fine_g'], self.fine(self.lots), 3)
        self.assertAlmostEqual(s['value'], s['fine_g'] * 245.80, 1)
        self.assertEqual(self.store2.jewellery_summary()['pieces'], 0)

    def test_dispatch_puts_pieces_in_transit_and_receive_lands_them(self):
        lots = self.lots[0] | self.lots[1]
        t = self.transfer(lots)
        self.assertTrue(t.name.startswith('TRF/'))
        self.assertAlmostEqual(t.fine_g, self.fine(lots), 3)
        t.with_user(self.staff).action_dispatch()
        self.assertEqual(t.state, 'in_transit')
        self.assertEqual(t.dispatched_by_id, self.staff)
        transit = self.env.ref('mumtaz_jewellery_stores.location_in_transit')
        self.assertEqual(self.lots[0].jewellery_current_location(), transit)
        self.assertEqual(self.store1.jewellery_summary()['pieces'], 4)
        self.assertEqual(self.store1.jewellery_summary()['in_transit_out']['pieces'], 2)
        self.assertFalse(self.env['jewellery.tray']._lot_available(self.lots[0]))   # not on any shelf
        # still ours: the quant exists, in an internal location (on no store's shelf, so not "in a warehouse")
        self.assertEqual(self.env['stock.quant'].sudo().search([('lot_id', '=', self.lots[0].id), ('location_id', '=', transit.id)]).quantity, 1)
        # the sending store cannot receive for the other store
        with self.assertRaises(UserError):
            t.with_user(self.staff).action_receive()
        t.with_user(self.staff2).action_receive()
        self.assertEqual(t.state, 'received')
        self.assertEqual(self.lots[0].jewellery_store(), self.store2)
        self.assertEqual(self.store2.jewellery_summary()['pieces'], 2)
        self.assertTrue(self.env['jewellery.tray']._lot_available(self.lots[0]))

    def test_only_shelf_pieces_travel_and_a_piece_cannot_be_in_two_transfers(self):
        lot = self.lots[2]
        t1 = self.transfer(lot)
        t1.with_user(self.staff).action_dispatch()
        t2 = self.transfer(lot)
        with self.assertRaises(UserError):
            t2.with_user(self.staff).action_dispatch()            # not on the shelf any more
        with self.assertRaises(UserError):
            self.transfer(self.lots[3], src=self.store1, dst=self.store1)
        t3 = self.transfer(self.lots[3], user=self.staff2)
        with self.assertRaises(UserError):
            t3.with_user(self.staff2).action_dispatch()

    def test_overdue_and_lost_make_cards_and_lost_keeps_the_metal_on_the_book(self):
        t = self.transfer(self.lots[4])
        t.with_user(self.staff).action_dispatch()
        t.sudo().write({'dispatched_at': fields.Datetime.now() - timedelta(days=3)})
        self.assertTrue(t.overdue)
        self.env['jewellery.owner.card'].refresh()
        Card = self.env['jewellery.owner.card'].sudo()
        self.assertTrue(Card.search([('kind', '=', 'store'), ('res_id', '=', t.id), ('title', 'ilike', 'overdue')]))
        with self.assertRaises(UserError):
            t.with_user(self.staff).action_report_lost('gone')
        t.with_user(self.maker).action_report_lost('Courier cannot find the bag.')
        self.assertEqual(t.state, 'lost')
        transit = self.env.ref('mumtaz_jewellery_stores.location_in_transit')
        self.assertEqual(self.env['stock.quant'].sudo().search([('lot_id', '=', self.lots[4].id), ('location_id', '=', transit.id)]).quantity, 1)  # owned, on no shelf
        self.env['jewellery.owner.card'].refresh()
        self.assertTrue(Card.search([('kind', '=', 'store'), ('res_id', '=', t.id), ('title', 'ilike', 'lost')]))

    def test_store_staff_see_their_own_store_only(self):
        mine = self.transfer(self.lots[5])
        other_lot = self.env['stock.lot'].create({'name': 'TEST-STORE2-1', 'product_id': self.product.id, 'gross_weight_g': 10.0})
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id, 'lot_id': other_lot.id, 'location_id': self.store2.lot_stock_id.id,
            'inventory_quantity': 1.0}).action_apply_inventory()
        store3 = _second_store(self.env, 'TEST Store 3', 'TS3')
        theirs = self.transfer(other_lot, user=self.maker, src=self.store2, dst=store3)
        self.assertIn(mine, self.Transfer.with_user(self.staff).search([]))
        self.assertNotIn(theirs, self.Transfer.with_user(self.staff).search([]))
        self.assertIn(theirs, self.Transfer.with_user(self.maker).search([]))


@tagged('post_install', '-at_install')
class TestReconciliation(StoresCase):

    def test_snapshot_count_variance_and_close(self):
        rec = self.Recon.with_user(self.staff).open_for(self.store1)
        self.assertTrue(rec.name.startswith('REC/'))
        self.assertEqual(rec.expected_count, 6)
        self.assertAlmostEqual(rec.expected_fine_g, self.fine(self.lots), 3)
        self.assertEqual(self.Recon.open_for(self.store1), rec)      # once per store per day
        # scan five of six, plus a stranger
        rec.with_user(self.staff).action_count([l.name for l in self.lots[:5]] + ['NOT-OURS-1'])
        self.assertEqual(rec.counted_count, 5)
        self.assertEqual(rec.missing_count, 1)
        self.assertAlmostEqual(rec.variance_fine_g, -self.fine(self.lots[5]), 3)
        self.assertEqual(rec.recon_dict(detail=True)['missing'], [self.lots[5].name])
        self.assertEqual(rec.extra_serials, 'NOT-OURS-1')
        self.env['jewellery.owner.card'].refresh()
        self.assertTrue(self.env['jewellery.owner.card'].sudo().search([('kind', '=', 'store'), ('res_id', '=', rec.id), ('title', 'ilike', 'missing')]))
        with self.assertRaises(UserError):
            rec.with_user(self.staff).action_close('x')          # a manager closes
        with self.assertRaises(UserError):
            rec.with_user(self.maker).action_close()             # a variance needs a note
        rec.with_user(self.maker).action_close('Found in the safe after closing; recount tomorrow.')
        self.assertEqual((rec.state, rec.closed_by_id), ('closed', self.maker))
        with self.assertRaises(UserError):
            rec.with_user(self.staff).action_count([self.lots[5].name])
        self.env['jewellery.owner.card'].refresh()
        self.assertFalse(self.env['jewellery.owner.card'].sudo().search([('kind', '=', 'store'), ('res_id', '=', rec.id), ('state', '=', 'open')]))

    def test_a_piece_in_transit_is_not_expected_on_the_shelf(self):
        t = self.transfer(self.lots[0])
        t.with_user(self.staff).action_dispatch()
        rec = self.Recon.open_for(self.store1)
        self.assertEqual(rec.expected_count, 5)
        rec.action_count([l.name for l in self.lots[1:]])
        self.assertEqual(rec.variance_fine_g, 0)

    def test_store2_staff_cannot_see_store1_runs(self):
        rec = self.Recon.open_for(self.store1)
        self.assertNotIn(rec, self.Recon.with_user(self.staff2).search([]))
        self.assertIn(rec, self.Recon.with_user(self.staff).search([]))


@tagged('post_install', '-at_install')
class TestJawharApiStores(TestJawharApiSale):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.store1 = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], order='id', limit=1)
        cls.store2 = _second_store(cls.env, 'TEST API Store 2', 'TA2')

    def test_transfer_and_reconciliation_through_the_door(self):
        self.sign_in('api_cashier')
        stores = self.api('/stores')['data']['items']
        s1 = next(s for s in stores if s['id'] == self.store1.id)
        self.assertGreaterEqual(s1['pieces'], 2)
        self.assertIsNotNone(s1['value'])
        err = self.api('/transfers', 'POST', {'from_id': self.store1.id, 'to_id': self.store2.id, 'serials': ['NOPE-1']}, status=400)
        self.assertIn('No such piece', err['error']['message'])
        t = self.api('/transfers', 'POST', {'from_id': self.store1.id, 'to_id': self.store2.id, 'serials': [self.lot_a.name], 'dispatch': True}, status=201)['data']
        self.assertEqual((t['state'], t['piece_count']), ('in_transit', 1))
        self.assertEqual(self.api('/stores')['data']['items'][0]['in_transit_out']['pieces'] + 0, 1)
        t = self.api('/transfers/%d/receive' % t['id'], 'POST')['data']
        self.assertEqual(t['state'], 'received')
        self.assertEqual(self.api('/stores/%d/pieces' % self.store2.id)['data']['total'], 1)
        rec = self.api('/reconciliations', 'POST', {'store_id': self.store2.id}, status=201)['data']
        self.assertEqual(rec['expected_count'], 1)
        rec = self.api('/reconciliations/%d/count' % rec['id'], 'POST', {'serials': []})['data']
        self.assertEqual(rec['missing'], [self.lot_a.name])
        err = self.api('/reconciliations/%d/close' % rec['id'], 'POST', {}, status=400)
        self.assertIn('variance', err['error']['message'])
        rec = self.api('/reconciliations/%d/count' % rec['id'], 'POST', {'serials': [self.lot_a.name.lower()]})['data']
        self.assertEqual(rec['variance_fine_g'], 0)
        rec = self.api('/reconciliations/%d/close' % rec['id'], 'POST', {})['data']
        self.assertEqual(rec['state'], 'closed')
        self.assertEqual(self.api('/reconciliations?store_id=%d' % self.store2.id)['data']['count'], 1)
