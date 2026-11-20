"""The rate feed drafts; a person approves. The adapter reads a 24K price
from a provider, converts it to the company's per-gram figure, and enters
a draft gold rate with source "feed". The maker-checker rule is the gold
rate model's own and is untouched here: prices stay on the previous
approved rate until a different person approves the draft."""
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
TROY_OUNCE_G = 31.1034768
PROVIDERS = [('fixture', 'Fixture (a value you type: tests and demos)'), ('json_url', 'JSON over HTTPS')]
UNITS = [('gram_24k', 'Per gram, 24K'), ('ounce_24k', 'Per troy ounce, 24K')]


class RateFeed(models.Model):
    _name = 'jewellery.rate.feed'
    _description = 'Gold rate feed (drafts for approval)'

    name = fields.Char(required=True, default='Gold rate feed')
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)
    provider = fields.Selection(PROVIDERS, required=True, default='fixture')
    url = fields.Char(help='HTTPS endpoint returning JSON.')
    json_path = fields.Char(help='Dotted path to the number inside the JSON, e.g. data.gold.usd_per_oz.')
    fixture_value = fields.Float(digits=(16, 4), help='The value the fixture provider returns.')
    unit = fields.Selection(UNITS, required=True, default='gram_24k')
    min_change_pct = fields.Float(default=0.0, help='Draft only when the value moves at least this much from the approved rate. 0: any change.')
    last_fetched_at = fields.Datetime(readonly=True)
    last_value = fields.Float(digits=(16, 4), readonly=True, help='Last converted value, per gram 24K.')
    last_rate_id = fields.Many2one('jewellery.gold.rate', readonly=True, string='Last draft')
    last_error = fields.Char(readonly=True)
    log_ids = fields.One2many('jewellery.rate.feed.log', 'feed_id')

    # -- reading the provider --------------------------------------------
    def _read_raw(self):
        self.ensure_one()
        if self.provider == 'fixture':
            if not self.fixture_value or self.fixture_value <= 0:
                raise UserError(_('The fixture value must be a positive number.'))
            return float(self.fixture_value)
        if not self.url or not self.url.lower().startswith('https://'):
            raise UserError(_('The feed URL must start with https://.'))
        resp = requests.get(self.url, timeout=10, headers={'Accept': 'application/json'})
        resp.raise_for_status()
        node = resp.json()
        for key in [k for k in (self.json_path or '').split('.') if k]:
            if isinstance(node, list):
                node = node[int(key)]
            elif isinstance(node, dict):
                node = node[key]
            else:
                raise UserError(_('The value path does not match the JSON.'))
        value = float(node)
        if value <= 0:
            raise UserError(_('The feed returned %s, not a positive number.') % node)
        return value

    def _to_per_gram(self, raw):
        return raw / TROY_OUNCE_G if self.unit == 'ounce_24k' else raw

    # -- the draft -----------------------------------------------------------
    def action_fetch(self):
        """Read the provider and enter a draft, or log why not. Never
        approves, never raises out of a cron."""
        self.ensure_one()
        Log = self.env['jewellery.rate.feed.log'].sudo()
        Rate = self.env['jewellery.gold.rate'].sudo()
        now = fields.Datetime.now()
        try:
            raw = self._read_raw()
            per_g = round(self._to_per_gram(raw), 4)
        except (UserError, requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            msg = str(exc)[:200]
            self.sudo().write({'last_fetched_at': now, 'last_error': msg})
            Log.create({'feed_id': self.id, 'error': msg})
            return {'ok': False, 'error': msg, 'rate': None}
        approved = Rate.search([('state', '=', 'approved'), ('company_id', '=', self.company_id.id)],
                               order='effective_at desc, id desc', limit=1)
        reason = None
        if approved and abs(approved.rate_per_gram - per_g) < 0.00005:
            reason = 'unchanged'
        elif approved and self.min_change_pct and abs(per_g - approved.rate_per_gram) / approved.rate_per_gram * 100 < self.min_change_pct:
            reason = 'below_min_change'
        pending = Rate.search([('state', '=', 'draft'), ('source', '=', 'feed'), ('company_id', '=', self.company_id.id),
                               ('rate_per_gram', '=', per_g)], limit=1)
        if pending:
            reason = 'draft_exists'
        rate = pending
        if not reason:
            rate = Rate.with_user(self.env.user).create({
                'rate_per_gram': per_g, 'source': 'feed', 'company_id': self.company_id.id,
                'currency_id': self.company_id.currency_id.id, 'effective_at': now,
            })
        self.sudo().write({'last_fetched_at': now, 'last_value': per_g, 'last_error': False,
                           'last_rate_id': rate.id if rate else self.last_rate_id.id})
        Log.create({'feed_id': self.id, 'raw_value': raw, 'rate_per_gram': per_g, 'rate_id': rate.id if rate else False, 'note': reason})
        return {'ok': True, 'raw': raw, 'rate_per_gram': per_g, 'rate': rate, 'skipped': reason}

    @api.model
    def _cron_fetch(self):
        for feed in self.sudo().search([('active', '=', True)]):
            try:
                feed.with_company(feed.company_id).action_fetch()
            except Exception as exc:  # noqa: BLE001 -- one feed must not stop the others
                _logger.warning('Rate feed %s: %s', feed.name, exc)

    def feed_dict(self):
        self.ensure_one()
        return {
            'id': self.id, 'name': self.name, 'active': self.active, 'provider': self.provider, 'url': self.url or None,
            'json_path': self.json_path or None, 'fixture_value': self.fixture_value, 'unit': self.unit,
            'min_change_pct': self.min_change_pct, 'last_fetched_at': self.last_fetched_at or None,
            'last_value': self.last_value, 'last_error': self.last_error or None,
            'last_rate': {'id': self.last_rate_id.id, 'rate_per_gram': self.last_rate_id.rate_per_gram, 'state': self.last_rate_id.state} if self.last_rate_id else None,
        }


class RateFeedLog(models.Model):
    _name = 'jewellery.rate.feed.log'
    _description = 'Gold rate feed fetch'
    _order = 'id desc'

    feed_id = fields.Many2one('jewellery.rate.feed', required=True, ondelete='cascade', index=True)
    raw_value = fields.Float(digits=(16, 4))
    rate_per_gram = fields.Float(digits=(16, 4))
    rate_id = fields.Many2one('jewellery.gold.rate', ondelete='set null')
    note = fields.Char()
    error = fields.Char()
