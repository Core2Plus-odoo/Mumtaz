"""Branded proposal renderer — the proposal agent's JSON → a client-ready,
in-brand document (HTML, and PDF when WeasyPrint is available).

Brand comes from the tenant's saved branding (store setting 'branding'),
falling back to C2P defaults, so the same renderer white-labels per tenant.
PDF is best-effort: if WeasyPrint (and its system libs) aren't installed we
return None and the caller attaches the HTML instead — the flow never breaks.
"""
from __future__ import annotations

from html import escape
from typing import Optional

_DEFAULT_BRAND = {
    "name": "C2P Consultants",
    "legal": "C2P Consultants FZC LLC",
    "tagline": "Beyond the Core.",
    "accent": "#00B3B3", "accentDark": "#008080", "ink": "#2E2E2E",
    "contact": "core2plus.com · info@core2plus.com · +971 58 128 2057",
    "address": "Ajman Free Zone, UAE · Trade Licence 34241",
    "confidential": "Confidential — prepared for the named client only.",
}


def brand(store) -> dict:
    b = {}
    try:
        b = store.get_setting("branding") or {}
    except Exception:
        b = {}
    out = dict(_DEFAULT_BRAND)
    out.update({k: v for k, v in b.items() if v})
    return out


def _aed(n) -> str:
    try:
        return "AED " + f"{float(n):,.0f}"
    except Exception:
        return f"AED {n}"


def _logo(b: dict) -> str:
    if b.get("logoDark"):
        return f'<img src="{b["logoDark"]}" alt="logo" style="height:46px">'
    ink = b.get("ink", "#2E2E2E")
    acc = b.get("accent", "#00B3B3")
    return (
        f'<svg viewBox="0 0 230 88" height="46" xmlns="http://www.w3.org/2000/svg">'
        f'<text x="0" y="54" font-family="Fraunces,Georgia,serif" font-weight="700" font-size="56" fill="{ink}">C2P</text>'
        f'<text x="3" y="80" font-family="DM Sans,sans-serif" font-weight="500" font-size="17" letter-spacing="2" fill="{ink}">Consultants</text>'
        f'<g fill="none" stroke="{acc}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M168 42 L190 20 L212 42"/><path d="M168 60 L190 38 L212 60"/></g></svg>'
    )


def _ul(items) -> str:
    items = items or []
    return "<ul>" + "".join(f"<li>{escape(str(x))}</li>" for x in items) + "</ul>" if items else "<p>—</p>"


def render_html(proposal: dict, company: str, b: dict, date_str: str = "") -> str:
    p = proposal or {}
    eff = p.get("effort_estimate") or []
    total_md = sum(float(r.get("man_days") or 0) for r in eff)
    comm = p.get("commercial") or {}
    phases = "".join(
        f"<div class='box'><b>{escape(str(ph.get('name','')))}</b>{_ul(ph.get('deliverables'))}</div>"
        for ph in (p.get("phases") or [])
    )
    eff_rows = "".join(
        f"<tr><td>{escape(str(r.get('workstream','')))}</td><td>{escape(str(r.get('role','')))}</td>"
        f"<td class='n'>{escape(str(r.get('man_days','')))}</td></tr>" for r in eff
    )
    timeline = "".join(
        f"<tr><td>{escape(str(t.get('milestone','')))}</td><td class='n'>Week {escape(str(t.get('week','')))}</td></tr>"
        for t in (p.get("timeline") or [])
    )
    accent, accent_dark, ink = b["accent"], b["accentDark"], b["ink"]
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Proposal — {escape(company)}</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans','Segoe UI',sans-serif;color:{ink};font-size:12px;line-height:1.6}}
h1,h2{{font-family:'Fraunces',Georgia,serif}}
.page{{padding:32mm 22mm 26mm;position:relative}}
.cover{{min-height:84vh;display:flex;flex-direction:column;page-break-after:always}}
.kicker{{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:{accent_dark};margin:26px 0 10px}}
.cover h1{{font-size:40px;line-height:1.05}}
.cover .co{{font-size:20px;color:#555;margin-top:18px}}
.cover .meta{{font-size:11px;color:#888;margin-top:26px;line-height:1.7}}
.cover .by{{margin-top:auto;font-size:12px;color:#666}}.cover .by b{{color:{ink}}}
.sec-head{{border-bottom:2px solid {accent};padding-bottom:8px;margin:0 0 14px}}
.sec-head h2{{font-size:20px}}
h3{{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:#888;margin:16px 0 7px;font-family:'JetBrains Mono',monospace}}
ul{{margin:0 0 8px 18px}}li{{margin-bottom:4px}}
.two{{display:flex;gap:24px}}.two>div{{flex:1}}
table{{width:100%;border-collapse:collapse;margin:6px 0 10px}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid #e6e9e8;font-size:11px}}
th{{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:.5px;text-transform:uppercase;color:#999}}
td.n,th.n{{text-align:right}}tr.tot td{{border-top:2px solid #ccc;font-weight:700}}
.box{{background:#f7f8f7;border:1px solid #e6e9e8;border-left:3px solid {accent};border-radius:8px;padding:12px 15px;margin:8px 0}}
.price{{font-family:'Fraunces',serif;font-weight:700;font-size:20px}}
.foot{{position:fixed;bottom:10mm;left:22mm;right:22mm;display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;font-size:8.5px;color:#aaa;border-top:1px solid #eee;padding-top:6px}}
@page{{size:A4;margin:0}}
</style></head><body>
<div class="cover"><div class="page" style="min-height:86vh;display:flex;flex-direction:column">
  <div style="height:46px">{_logo(b)}</div>
  <div class="kicker">{escape(b['tagline'])} · Commercial Proposal</div>
  <h1>Odoo Solution<br>Proposal</h1>
  <div class="co">{escape(company)}</div>
  <div class="meta">{escape(date_str)}<br>Prepared by <b>{escape(b['legal'])}</b><br>{escape(b['address'])}<br>{escape(b['contact'])}</div>
  <div class="by">{escape(b['confidential'])}</div>
</div></div>

<div class="page">
  <div class="sec-head"><h2>Solution Proposal</h2></div>
  <div class="box">{escape(str(p.get('solution_summary','')))}</div>
  <div class="two"><div><h3>In scope</h3>{_ul(p.get('in_scope'))}</div>
    <div><h3>Out of scope</h3>{_ul(p.get('out_of_scope'))}</div></div>
  <h3>Phases &amp; deliverables</h3>{phases or '<p>—</p>'}
  <h3>Effort estimate</h3>
  <table><thead><tr><th>Workstream</th><th>Role</th><th class="n">Man-days</th></tr></thead>
    <tbody>{eff_rows}<tr class="tot"><td>Total</td><td></td><td class="n">{total_md:.0f}</td></tr></tbody></table>
  <h3>Commercial</h3>
  <div class="box"><span class="price">{escape(_aed(comm.get('estimate_aed')))}</span> · {escape(str(comm.get('pricing_model','')))}<br>
    <span style="color:#777">{escape(str(comm.get('vat_note','')))} — {escape(str(comm.get('licensing_note','')))}</span></div>
  {('<h3>Indicative timeline</h3><table><tbody>'+timeline+'</tbody></table>') if timeline else ''}
  <div class="two"><div><h3>Assumptions</h3>{_ul(p.get('assumptions'))}</div>
    <div><h3>Success criteria</h3>{_ul(p.get('success_criteria'))}</div></div>
</div>
<div class="foot"><span>{escape(b['name'])} · {escape(company)}</span><span>{escape(b['confidential'])}</span></div>
</body></html>"""


def to_pdf(html: str) -> Optional[bytes]:
    """Render HTML → PDF via WeasyPrint if installed; else None (caller attaches
    the HTML instead). Keeps PDF an optional capability, never a hard dependency."""
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()
    except Exception:
        return None
