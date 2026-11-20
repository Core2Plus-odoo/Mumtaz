"""Channels: the feed drafts and a person approves; a JSON provider is read
by path and unit; errors are logged, nothing raised; the publication switch
decides the public shelf; the door."""
from unittest.mock import patch

import requests

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.mumtaz_jewellery_api.tests.test_api import TestJawharApiSale
from odoo.addons.mumtaz_jewellery_crm.tests.test_tray import TrayCase


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('%s' % self.status_code)

    def json(self):
        return self._payload


@tagged('post_install', '-at_install')
class TestRateFeed(TrayCase):

    def setUp(self):
        super().setUp()
        self.Feed = self.env['jewellery.rate.feed'].with_user(self.maker)
        self.Rate = self.env['jewellery.gold.rate']

    def test_the_fixture_feed_drafts_and_never_approves(self):
        feed = self.Feed.create({'provider': 'fixture', 'fixture_value': 250.0})
        out = feed.action_fetch()
        self.assertTrue(out['ok'])
        draft = out['rate']
        self.assertEqual((draft.state, draft.source, draft.rate_per_gram), ('draft', 'feed', 250.0))
        # prices stay on the approved rate until a different person approves
        self.assertEqual(self.Rate.get_current(self.env.company).rate_per_gram, 245.80)
        with self.assertRaises(UserError):
            draft.with_user(self.maker).action_approve()          # the maker entered it; cannot approve his own
        draft.with_user(self.checker).action_approve()
        self.assertEqual(self.Rate.get_current(self.env.company).rate_per_gram, 250.0)
        log = feed.log_ids[0]
        self.assertEqual((log.raw_value, log.rate_per_gram, log.rate_id), (250.0, 250.0, draft))
        # read again, same value: no second draft
        out = feed.action_fetch()
        self.assertEqual(out['skipped'], 'unchanged')
        self.assertEqual(self.Rate.search_count([('source', '=', 'feed')]), 1)
        self.assertFalse(feed.last_error)

    def test_a_json_provider_is_read_by_path_and_ounces_become_grams(self):
        feed = self.Feed.create({'provider': 'json_url', 'url': 'https://feed.example/gold', 'json_path': 'data.items.0.usd_oz',
                                 'unit': 'ounce_24k'})
        payload = {'data': {'items': [{'usd_oz': 7776.0}]}}
        with patch('requests.get', return_value=_Resp(payload)) as get:
            out = feed.action_fetch()
        self.assertTrue(out['ok'])
        self.assertAlmostEqual(out['rate_per_gram'], 7776.0 / 31.1034768, 3)
        self.assertEqual(get.call_args.kwargs['timeout'], 10)
        self.assertEqual(out['rate'].state, 'draft')

    def test_errors_are_logged_not_raised_and_http_is_refused(self):
        feed = self.Feed.create({'provider': 'json_url', 'url': 'http://feed.example/gold', 'json_path': 'x'})
        out = feed.action_fetch()
        self.assertFalse(out['ok'])
        self.assertIn('https', out['error'])
        feed.url = 'https://feed.example/gold'
        with patch('requests.get', side_effect=requests.ConnectionError('down')):
            out = feed.action_fetch()
        self.assertFalse(out['ok'])
        self.assertEqual(feed.last_error, 'down')
        with patch('requests.get', return_value=_Resp({'y': 1})):
            out = feed.action_fetch()
        self.assertFalse(out['ok'])
        self.assertEqual(len(feed.log_ids.filtered('error')), 3)
        self.assertFalse(self.Rate.search([('source', '=', 'feed')]))
        self.env['jewellery.rate.feed']._cron_fetch()               # a cron pass with a broken feed is quiet

    def test_min_change_and_a_second_draft_of_the_same_value(self):
        feed = self.Feed.create({'provider': 'fixture', 'fixture_value': 246.0, 'min_change_pct': 1.0})
        self.assertEqual(feed.action_fetch()['skipped'], 'below_min_change')
        feed.fixture_value = 260.0
        first = feed.action_fetch()['rate']
        self.assertEqual(first.state, 'draft')
        self.assertEqual(feed.action_fetch()['skipped'], 'draft_exists')
        self.assertEqual(self.Rate.search_count([('source', '=', 'feed')]), 1)

    def test_only_a_manager_configures(self):
        with self.assertRaises(AccessError):
            self.env['jewellery.rate.feed'].with_user(self.staff).create({'provider': 'fixture', 'fixture_value': 1})


@tagged('post_install', '-at_install')
class TestPublication(TrayCase):

    def test_an_unpublished_design_leaves_the_public_shelf_but_not_the_staff_screens(self):
        Tray = self.env['jewellery.tray']
        lot = self.lots[0]
        self.assertTrue(Tray._lot_public(lot))
        self.product.product_tmpl_id.jewellery_published = False
        self.assertFalse(Tray._lot_public(lot))
        self.assertTrue(Tray._lot_available(lot))                    # staff still sell it
        with self.assertRaises(UserError):
            self.env['jewellery.kiosk.request'].create_public('viewing', lot.name, 'Hind Walk-in', '+971500009001')


@tagged('post_install', '-at_install')
class TestJawharApiChannels(TestJawharApiSale):

    def test_feed_shelf_and_requests_through_the_door(self):
        self.sign_in('api_seller')
        self.assertEqual(self.api('/channels/feed', 'POST', {'provider': 'fixture', 'fixture_value': 251}, status=403)['error']['code'], 'forbidden')
        self.api('/auth/logout', 'POST')
        self.sign_in('api_cashier')
        f = self.api('/channels/feed', 'POST', {'provider': 'fixture', 'fixture_value': 251, 'unit': 'gram_24k', 'name': 'Test feed'})['data']
        self.assertEqual(f['provider'], 'fixture')
        out = self.api('/channels/feed/fetch', 'POST')['data']
        self.assertTrue(out['ok'])
        self.assertEqual((out['rate']['state'], out['rate']['source'], out['rate']['rate_per_gram']), ('draft', 'feed', 251.0))
        self.assertEqual(self.api('/rates/current')['data']['rate']['rate_per_gram'], 245.8)   # unchanged until approved
        feed = self.api('/channels/feed')['data']
        self.assertEqual(feed['logs'][0]['rate_per_gram'], 251.0)
        shelf = self.api('/channels/shelf')['data']
        tmpl = next(i for i in shelf['items'] if i['id'] == self.product.product_tmpl_id.id)
        self.assertTrue(tmpl['published'])
        self.assertGreaterEqual(tmpl['on_shelf'], 2)
        before = shelf['public_count']
        self.api('/channels/shelf/%d' % tmpl['id'], 'POST', {'published': False})
        after = self.api('/channels/shelf')['data']['public_count']
        self.assertEqual(before - after, tmpl['on_shelf'])
        pub = self.url_open('/jawhar/public/kiosk/pieces?limit=12').json()['data']
        self.assertNotIn(self.lot_a.name, [p['serial'] for p in pub['items']])
        self.api('/channels/shelf/%d' % tmpl['id'], 'POST', {'published': True})
        reqs = self.api('/channels/requests?days=30')['data']['channels']
        self.assertIn('store', reqs)
        self.assertIn('web', reqs)
