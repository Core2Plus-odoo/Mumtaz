"""Stock import: a jeweller's existing stock book, as a spreadsheet, into
serial-tracked pieces on a store's shelf. Preview first (nothing written),
then apply; rows with a problem are reported by line and never half-written.
A serial already in the book is skipped, so the same file can be loaded
twice. Every run is written down (`jewellery.piece.import`)."""
import csv
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .product import KARATS, MAKING_TYPES

_logger = logging.getLogger(__name__)
CATEGORIES = ('bangle', 'chain', 'necklace', 'ring', 'earrings', 'bracelet', 'pendant', 'set', 'coin')
COLUMNS = ('serial', 'design', 'category', 'karat', 'gross_g', 'stone_g', 'stones_value', 'wastage_pct',
           'making_type', 'making_value', 'rfid', 'certificate', 'cost', 'store')
REQUIRED = ('serial', 'design', 'karat', 'gross_g')
ALIASES = {'serial_number': 'serial', 'serial no': 'serial', 'sku': 'serial', 'product': 'design', 'name': 'design',
           'gross': 'gross_g', 'gross_weight': 'gross_g', 'gross_weight_g': 'gross_g', 'stone': 'stone_g',
           'stone_weight': 'stone_g', 'stone_weight_g': 'stone_g', 'stones': 'stones_value', 'wastage': 'wastage_pct',
           'making': 'making_value', 'rfid_tag': 'rfid', 'certificate_ref': 'certificate', 'cert': 'certificate',
           'cost_value': 'cost', 'warehouse': 'store', 'branch': 'store', 'purity': 'karat', 'kt': 'karat'}
MAX_ROWS = 2000


def _norm(key):
    k = (key or '').strip().lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
    return ALIASES.get(k, k)


def rows_from_csv(text):
    """Rows (dicts with normalised column names) from CSV text; the delimiter is sniffed."""
    text = (text or '').lstrip('﻿')
    if not text.strip():
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [{_norm(k): (v or '').strip() for k, v in row.items() if k is not None} for row in reader][:MAX_ROWS]


def rows_from_xlsx(data):
    """Rows from the first sheet of a workbook (bytes); the first row is the header."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - openpyxl ships with Odoo
        raise UserError(_('Spreadsheet import needs openpyxl on the server.')) from exc
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [_norm(str(h)) if h is not None else '' for h in next(it, [])]
    out = []
    for values in it:
        if values is None or all(v in (None, '') for v in values):
            continue
        out.append({header[i]: ('' if v is None else str(v).strip()) for i, v in enumerate(values) if i < len(header) and header[i]})
        if len(out) >= MAX_ROWS:
            break
    return out


class PieceImport(models.Model):
    _name = 'jewellery.piece.import'
    _description = 'Stock import run'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda s: _('Import'))
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    user_id = fields.Many2one('res.users', required=True, default=lambda s: s.env.user)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Store')
    rows = fields.Integer()
    created = fields.Integer()
    skipped = fields.Integer()
    errors = fields.Integer()
    report = fields.Text(help='One line per row that was skipped or refused.')

    # -- checking ----------------------------------------------------------
    @api.model
    def _check_rows(self, rows, warehouse=None):
        """Every row judged, nothing written. Returns (results, products_needed):
        results is a list per row with status new / exists / error."""
        Lot = self.env['stock.lot'].sudo()
        Template = self.env['product.template'].sudo()
        Warehouse = self.env['stock.warehouse'].sudo()
        karats = dict(KARATS)
        making_types = dict(MAKING_TYPES)
        seen = set()
        out = []
        for i, row in enumerate(rows, start=2):           # line 1 is the header
            r = {'line': i, 'serial': (row.get('serial') or '').strip()[:40], 'design': (row.get('design') or '').strip()[:80],
                 'status': 'new', 'message': ''}
            problems = []
            for key in REQUIRED:
                if not (row.get(key) or '').strip():
                    problems.append(_('%s is missing') % key)
            if r['serial'] in seen:
                problems.append(_('serial repeats in the file'))
            seen.add(r['serial'])
            karat = (row.get('karat') or '').strip().upper().rstrip('K')
            if karat and karat not in karats:
                problems.append(_('karat must be one of %s') % ', '.join(karats))
            category = (row.get('category') or '').strip().lower()
            if category and category not in CATEGORIES:
                problems.append(_('category must be one of %s') % ', '.join(CATEGORIES))
            making_type = (row.get('making_type') or 'percent').strip().lower() or 'percent'
            if making_type not in making_types:
                problems.append(_('making_type must be one of %s') % ', '.join(making_types))
            nums = {}
            for key in ('gross_g', 'stone_g', 'stones_value', 'wastage_pct', 'making_value', 'cost'):
                raw = (row.get(key) or '').replace(',', '').strip()
                if not raw:
                    nums[key] = 0.0
                    continue
                try:
                    nums[key] = float(raw)
                except ValueError:
                    problems.append(_('%s is not a number') % key)
                    nums[key] = 0.0
            if nums['gross_g'] <= 0 and 'gross_g' not in [p.split(' ')[0] for p in problems]:
                problems.append(_('gross_g must be above zero'))
            if nums['stone_g'] < 0 or nums['stone_g'] >= nums['gross_g'] and nums['gross_g'] > 0:
                problems.append(_('stone_g must be below gross_g'))
            wh = warehouse
            code = (row.get('store') or '').strip()
            if code:
                wh = Warehouse.search([('code', '=ilike', code), ('company_id', '=', self.env.company.id)], limit=1) \
                    or Warehouse.search([('name', '=ilike', code), ('company_id', '=', self.env.company.id)], limit=1)
                if not wh:
                    problems.append(_('store %s is not known') % code)
            if problems:
                r.update(status='error', message='; '.join(problems))
                out.append(r)
                continue
            if r['serial'] and Lot.search_count([('name', '=', r['serial']), ('product_id.is_jewellery', '=', True)]):
                r.update(status='exists', message=_('already in the stock book'))
                out.append(r)
                continue
            rfid = (row.get('rfid') or '').strip()[:60]
            if rfid and Lot.search_count([('rfid_tag', '=', rfid), ('company_id', '=', self.env.company.id)]):
                r.update(status='error', message=_('RFID tag %s is already on another piece') % rfid)
                out.append(r)
                continue
            template = Template.search([('name', '=ilike', r['design']), ('is_jewellery', '=', True)], limit=1)
            r.update(values={
                'template': template, 'category': category or (template.jewellery_category if template else False),
                'karat': karat, 'making_type': making_type, 'rfid': rfid,
                'certificate': (row.get('certificate') or '').strip()[:80], 'warehouse': wh, **nums,
            }, message=_('new design') if not template else '')
            out.append(r)
        return out

    @api.model
    def preview(self, rows, warehouse=None):
        results = self._check_rows(rows, warehouse)
        return {'rows': [{k: v for k, v in r.items() if k != 'values'} for r in results],
                'summary': self._summary(results)}

    @staticmethod
    def _summary(results):
        return {'rows': len(results), 'new': sum(r['status'] == 'new' for r in results),
                'exists': sum(r['status'] == 'exists' for r in results), 'errors': sum(r['status'] == 'error' for r in results)}

    # -- writing -------------------------------------------------------------
    @api.model
    def apply(self, rows, warehouse=None, skip_errors=False, name=None):
        """Create the new pieces on the shelf of their store. Refuses the whole
        file when a row is wrong unless skip_errors; a run is one transaction,
        so a failure half-way writes nothing."""
        if not self.env.user.has_group('mumtaz_jewellery.group_jewellery_manager'):
            raise UserError(_('Only a jewellery manager may import stock.'))
        if len(rows) > MAX_ROWS:
            raise UserError(_('At most %s rows per file.') % MAX_ROWS)
        wh = warehouse or self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        if not wh:
            raise UserError(_('No store (warehouse) to put the pieces in.'))
        results = self._check_rows(rows, wh)
        summary = self._summary(results)
        if summary['errors'] and not skip_errors:
            raise UserError(_('%s row(s) have a problem; fix them or import with skip_errors.') % summary['errors'])
        Template = self.env['product.template'].sudo()
        Lot = self.env['stock.lot'].sudo()
        Quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True)
        storable = 'is_storable' in Template._fields
        made = {}
        for r in results:
            if r['status'] != 'new':
                continue
            v = r['values']
            template = v['template'] or made.get(r['design'].lower())
            if not template:
                vals = {'name': r['design'], 'is_jewellery': True, 'tracking': 'serial', 'jewellery_category': v['category'] or False,
                        'jewellery_karat': v['karat'], 'jewellery_wastage_pct': v['wastage_pct'],
                        'jewellery_making_type': v['making_type'], 'jewellery_making_value': v['making_value'],
                        'company_id': self.env.company.id}
                if storable:
                    vals.update(type='consu', is_storable=True)
                else:  # pragma: no cover - older stock
                    vals['type'] = 'product'
                template = Template.create(vals)
                made[r['design'].lower()] = template
            lot = Lot.create({
                'name': r['serial'], 'product_id': template.product_variant_id.id, 'company_id': self.env.company.id,
                'gross_weight_g': v['gross_g'], 'stone_weight_g': v['stone_g'], 'stones_value': v['stones_value'],
                'karat': v['karat'] or template.jewellery_karat, 'wastage_pct': v['wastage_pct'] or template.jewellery_wastage_pct,
                'making_type': v['making_type'], 'making_value': v['making_value'] or template.jewellery_making_value,
                'rfid_tag': v['rfid'] or False, 'certificate_ref': v['certificate'] or False,
                'jewellery_cost_value': v['cost'],
            })
            Quant.create({'product_id': lot.product_id.id, 'lot_id': lot.id,
                          'location_id': (v['warehouse'] or wh).lot_stock_id.id, 'inventory_quantity': 1.0}).action_apply_inventory()
            r['lot_id'] = lot.id
        report = '\n'.join('%s %s: %s' % (r['line'], r['serial'], r['message']) for r in results if r['status'] != 'new')
        run = self.create({'name': name or _('Import of %s rows') % len(rows), 'warehouse_id': wh.id, 'rows': summary['rows'],
                           'created': summary['new'], 'skipped': summary['exists'], 'errors': summary['errors'], 'report': report or False})
        _logger.info('Stock import %s by %s: %s', run.id, self.env.user.login, summary)
        return {'import_id': run.id, 'rows': [{k: v for k, v in r.items() if k != 'values'} for r in results], 'summary': summary}

    @api.model
    def template_csv(self):
        return ','.join(COLUMNS) + '\n'
