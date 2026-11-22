"""Next-best-offer ranking. Pure Python, no Odoo imports, deterministic.

Every score component is returned as a reason so staff see *why* a piece is
suggested. The model never prices anything; price and margin come from the
caller (approved rate in the database).
"""


def rank_pieces(prefs, pieces, limit=5):
    """prefs: dict(karats=[...], budget=float|None, bought_ids=set(), occasion=str|None)
    pieces: list of dict(id, name, karat, price, margin_pct, category, occasions=[...])
    Returns list of dict(id, name, score, reasons[], price, margin_pct) best first."""
    karats = set(prefs.get('karats') or [])
    budget = prefs.get('budget')
    bought = set(prefs.get('bought_ids') or [])
    occasion = prefs.get('occasion')
    out = []
    for p in pieces:
        if p['id'] in bought:
            continue
        score, reasons = 0.0, []
        if karats and p['karat'] in karats:
            score += 30
            reasons.append('Matches preferred karat %sK' % p['karat'])
        if budget:
            ratio = p['price'] / budget if budget else 0
            if 0.6 <= ratio <= 1.3:
                score += 30
                reasons.append('Within usual spend (%.0f%% of typical)' % (ratio * 100))
            elif ratio > 1.3:
                score += 10
                reasons.append('Upgrade: %.0f%% above usual spend' % (ratio * 100))
        if occasion and occasion in (p.get('occasions') or []):
            score += 25
            reasons.append('Suits upcoming %s' % occasion)
        m = p.get('margin_pct') or 0
        score += min(m, 30) / 3.0
        if m:
            reasons.append('Margin %.0f%%' % m)
        out.append({'id': p['id'], 'name': p['name'], 'score': round(score, 1),
                    'reasons': reasons, 'price': p['price'], 'margin_pct': m})
    out.sort(key=lambda x: (-x['score'], x['id']))
    return out[:limit]
