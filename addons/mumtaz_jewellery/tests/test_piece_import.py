"""A stock book comes in as a spreadsheet: checked first, written once,
loadable twice without doubling."""
import io

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import JewelCommon
from ..models.piece_import import rows_from_csv, rows_from_xlsx

CSV = """Serial,Design,Category,Karat,Gross (g),Stone g,Stones value,Wastage %,Making type,Making value,RFID,Certificate,Cost,Store
IMP-0001,Imported Bangle 22K,bangle,22K,24.5,0,0,2,percent,10,IMP-RFID-1,,5100,
IMP-0002,Imported Ring 18K,ring,18,6.4,1.1,1800,1,fixed,250,,CERT-1,2200,
IMP-0003,Imported Bangle 22K,bangle,22,31.2,0,0,2,percent,10,,,6400,
"""


@tagged('post_install', '-at_install', 'mumtaz_jewel')
class TestPieceImport(JewelCommon):

    def setUp(self):
        super().setUp()
        self.Import = self.env['jewellery.piece.import'].with_user(self.user_manager_a)

    def test_the_header_is_read_loosely(self):
        rows = rows_from_csv(CSV)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['serial'], 'IMP-0001')
        self.assertEqual(rows[0]['gross_g'], '24.5')
        self.assertEqual(rows[1]['certificate'], 'CERT-1')
        semi = rows_from_csv('serial;design;karat;gross_g\nIMP-9;X;22;5\n')
        self.assertEqual(semi[0]['gross_g'], '5')

    def test_preview_judges_every_row_and_writes_nothing(self):
        rows = rows_from_csv(CSV + 'IMP-0004,Bad Row,ring,19,abc,0,0,0,percent,0,,,,\n'
                                   'IMP-0001,Imported Bangle 22K,bangle,22,20,0,0,2,percent,10,,,,\n'
                                   ',No Serial,ring,18,5,0,0,0,fixed,0,,,,\n')
        out = self.Import.preview(rows)
        self.assertEqual(out['summary'], {'rows': 6, 'new': 3, 'exists': 0, 'errors': 3})
        by = {r['line']: r for r in out['rows']}
        self.assertIn('karat', by[5]['message']); self.assertIn('gross_g', by[5]['message'])
        self.assertIn('repeats', by[6]['message'])
        self.assertIn('serial is missing', by[7]['message'])
        self.assertEqual(by[2]['message'], 'new design')
        self.assertFalse(self.env['stock.lot'].search([('name', 'like', 'IMP-%')]))
        self.assertFalse(self.env['jewellery.piece.import'].search([]))

    def test_apply_creates_designs_and_pieces_on_the_shelf_once(self):
        self._approved_rate(rate=100.0)
        out = self.Import.apply(rows_from_csv(CSV), name='TEST book')
        self.assertEqual(out['summary'], {'rows': 3, 'new': 3, 'exists': 0, 'errors': 0})
        lots = self.env['stock.lot'].search([('name', 'like', 'IMP-%')], order='name')
        self.assertEqual(len(lots), 3)
        bangle = lots[0]
        self.assertEqual(bangle.product_id.name, 'Imported Bangle 22K')
        self.assertEqual(bangle.product_id.jewellery_category, 'bangle')
        self.assertEqual(bangle.karat, '22')
        self.assertEqual(bangle.rfid_tag, 'IMP-RFID-1')
        self.assertEqual(bangle.jewellery_cost_value, 5100.0)
        self.assertEqual(bangle.product_qty, 1.0, 'on the shelf')
        self.assertEqual(lots[2].product_id, bangle.product_id, 'the same design is created once')
        self.assertEqual(lots[1].certificate_ref, 'CERT-1')
        self.assertGreater(lots[1].jewellery_price, 0, 'priced from the approved rate')
        run = self.env['jewellery.piece.import'].browse(out['import_id'])
        self.assertEqual((run.created, run.skipped, run.errors), (3, 0, 0))
        again = self.Import.apply(rows_from_csv(CSV))
        self.assertEqual(again['summary'], {'rows': 3, 'new': 0, 'exists': 3, 'errors': 0})
        self.assertEqual(len(self.env['stock.lot'].search([('name', 'like', 'IMP-%')])), 3)

    def test_errors_refuse_the_file_unless_skipped_and_only_managers_import(self):
        rows = rows_from_csv(CSV + 'IMP-0004,Bad Row,ring,19,abc,0,0,0,percent,0,,,,\n')
        with self.assertRaises(UserError):
            self.Import.apply(rows)
        self.assertFalse(self.env['stock.lot'].search([('name', 'like', 'IMP-%')]))
        out = self.Import.apply(rows, skip_errors=True)
        self.assertEqual(out['summary']['new'], 3)
        self.assertEqual(out['summary']['errors'], 1)
        self.assertIn('IMP-0004', self.env['jewellery.piece.import'].browse(out['import_id']).report)
        with self.assertRaises(UserError):
            self.env['jewellery.piece.import'].with_user(self.user_staff).apply(rows_from_csv(CSV))

    def test_a_workbook_reads_like_the_csv(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Serial', 'Design', 'Karat', 'Gross g', 'Stone g'])
        ws.append(['IMP-X1', 'Sheet Chain 21K', 21, 18.75, None])
        ws.append([None, None, None, None, None])
        buf = io.BytesIO(); wb.save(buf)
        rows = rows_from_xlsx(buf.getvalue())
        self.assertEqual(rows, [{'serial': 'IMP-X1', 'design': 'Sheet Chain 21K', 'karat': '21', 'gross_g': '18.75', 'stone_g': ''}])
        out = self.Import.preview(rows)
        self.assertEqual(out['summary']['new'], 1)
