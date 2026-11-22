import importlib.util
import os
import unittest

_p = os.path.join(os.path.dirname(__file__), '..', 'services', 'nbo.py')
_s = importlib.util.spec_from_file_location('nbo', _p)
nbo = importlib.util.module_from_spec(_s)
_s.loader.exec_module(nbo)

PIECES = [
    {'id': 1, 'name': 'A', 'karat': '22', 'price': 10000, 'margin_pct': 12, 'occasions': ['wedding']},
    {'id': 2, 'name': 'B', 'karat': '18', 'price': 9000, 'margin_pct': 20, 'occasions': []},
    {'id': 3, 'name': 'C', 'karat': '22', 'price': 30000, 'margin_pct': 15, 'occasions': []},
]


class TestNbo(unittest.TestCase):
    def test_karat_and_budget_win(self):
        r = nbo.rank_pieces({'karats': ['22'], 'budget': 10000}, PIECES)
        self.assertEqual(r[0]['id'], 1)
        self.assertTrue(any('karat' in x for x in r[0]['reasons']))

    def test_already_bought_excluded(self):
        r = nbo.rank_pieces({'karats': ['22'], 'budget': 10000, 'bought_ids': {1}}, PIECES)
        self.assertNotIn(1, [x['id'] for x in r])

    def test_occasion_boost(self):
        r = nbo.rank_pieces({'karats': [], 'budget': 10000, 'occasion': 'wedding'}, PIECES)
        self.assertEqual(r[0]['id'], 1)

    def test_deterministic(self):
        a = nbo.rank_pieces({'karats': ['22'], 'budget': 10000}, PIECES)
        b = nbo.rank_pieces({'karats': ['22'], 'budget': 10000}, list(reversed(PIECES)))
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
