/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

/* Standard-format financial statements, computed live from posted entries.
   Self-contained OWL client action: builds its markup imperatively inside a
   single root <div> and renders the flat row lists the controller returns. */

const SHELL = `
  <header class="fs-top">
    <div class="fs-top-in">
      <div class="fs-brand">
        <div class="fs-mark">₨</div>
        <div><div class="fs-bname" data-el="company">Financial Statements</div>
          <div class="fs-bsub">Statement of accounts</div></div>
      </div>
      <div class="fs-sp"></div>
      <div class="fs-dates">
        <label>From <input type="date" data-el="from"/></label>
        <label>To <input type="date" data-el="to"/></label>
        <button class="fs-btn" data-el="apply">Apply</button>
      </div>
      <button class="fs-btn fs-tgl" data-el="theme"><span data-el="themeIco">☾</span><span data-el="themeLbl">Dark</span></button>
    </div>
  </header>

  <div class="fs-wrap">
    <div class="fs-bar">
      <div class="fs-tabs" data-el="tabs">
        <button data-view="pl" aria-selected="true">Profit &amp; Loss</button>
        <button data-view="bs" aria-selected="false">Balance Sheet</button>
        <button data-view="tb" aria-selected="false">Trial Balance</button>
        <button data-view="aged" aria-selected="false">Aged Partners</button>
      </div>
      <div class="fs-toolbar">
        <button class="fs-btn" data-el="fold">⇕ Collapse all</button>
        <button class="fs-btn fs-primary" data-el="print">⤓ Print / PDF</button>
      </div>
    </div>
    <div data-el="view"><div class="fs-loading">Loading…</div></div>
  </div>
`;

const AGED_COLORS = ["#0c7a4a", "#2a78d6", "#b5820a", "#c0392b"];
const AGED_LABELS = ["Current", "1–30 days", "31–60 days", "60+ days"];

class FinancialStatements extends Component {
    static template = "mumtaz_financial_reports.Statements";

    setup() {
        this.rootRef = useRef("root");
        this.action = useService("action");
        this.report = "pl";
        this.meta = {};
        this.allCollapsed = false;
        onMounted(() => {
            this.root = this.rootRef.el;
            if (!this.root) return;
            this.root.innerHTML = SHELL;
            this._wire();
            this._load();
        });
    }

    // -- helpers ---------------------------------------------------------
    q(name) { return this.root.querySelector(`[data-el="${name}"]`); }

    fmt(n) {
        if (!n) return "–";
        const a = Math.abs(Math.round(n)).toLocaleString("en-US");
        return n < 0 ? "(" + a + ")" : a;
    }
    pct(c, p) {
        if (!p) return { t: "", c: "mut" };
        const v = (c - p) / Math.abs(p) * 100;
        return { t: (v >= 0 ? "+" : "") + v.toFixed(1) + "%", c: v > 0 ? "up" : v < 0 ? "dn" : "mut" };
    }
    // "2025-07-01","2026-06-30" -> "FY 2025–26"; same year -> "FY 2026"
    fyLabel(f, t) {
        if (!f || !t) return "Current";
        const fy = +f.slice(0, 4), ty = +t.slice(0, 4);
        return fy === ty ? `FY ${ty}` : `FY ${fy}–${String(ty).slice(-2)}`;
    }
    shiftYear(d) { return d ? (+d.slice(0, 4) - 1) + d.slice(4) : d; }
    fmtDate(iso) {
        if (!iso) return "";
        const M = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const [y, m, d] = iso.split("-");
        return `${+d} ${M[+m - 1]} ${y}`;
    }

    _wire() {
        this.q("tabs").querySelectorAll("button").forEach((b) => {
            b.addEventListener("click", () => {
                this.q("tabs").querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", x === b));
                this.report = b.dataset.view;
                this._load();
            });
        });
        this.q("apply").addEventListener("click", () => this._load());
        this.q("fold").addEventListener("click", () => this._toggleAll());
        this.q("print").addEventListener("click", () => window.print());
        this.q("theme").addEventListener("click", () => {
            const dark = this.root.getAttribute("data-theme") === "dark";
            this.root.setAttribute("data-theme", dark ? "light" : "dark");
            this._syncTheme();
        });
        this._syncTheme();
        // event-delegated fold + drill
        this.q("view").addEventListener("click", (e) => {
            const head = e.target.closest("tr.r-fold");
            if (head) {
                const collapsed = head.classList.toggle("r-collapsed");
                this._group(head.dataset.g, collapsed);
                return;
            }
            const line = e.target.closest("tr.drill[data-acc]");
            if (line && line.dataset.acc) this._drill(line.dataset.acc.split(",").map(Number));
        });
    }

    _syncTheme() {
        const dark = this.root.getAttribute("data-theme") === "dark";
        this.q("themeIco").textContent = dark ? "☀" : "☾";
        this.q("themeLbl").textContent = dark ? "Light" : "Dark";
    }

    async _load() {
        const args = { report: this.report };
        const f = this.q("from").value, t = this.q("to").value;
        if (f) args.date_from = f;
        if (t) args.date_to = t;
        this.q("view").innerHTML = `<div class="fs-loading">Loading…</div>`;
        let res;
        try {
            res = await rpc("/mumtaz_financial_reports/data", args);
        } catch {
            this.q("view").innerHTML = `<div class="fs-loading">Could not load — check that Accounting is installed and entries are posted.</div>`;
            return;
        }
        this.meta = res.meta || {};
        this.cur = this.meta.currency || "";
        this.q("company").textContent = this.meta.company || "Financial Statements";
        if (this.meta.date_from && !this.q("from").value) this.q("from").value = this.meta.date_from;
        if (this.meta.date_to && !this.q("to").value) this.q("to").value = this.meta.date_to;
        this.allCollapsed = false;
        this.q("fold").textContent = "⇕ Collapse all";
        if (this.report === "aged") this._renderAged(res);
        else this._renderStmt(res.rows || [], res.tiles || []);
    }

    // -- statement renderer ---------------------------------------------
    _renderStmt(rows, tiles) {
        const hasLines = {}; let g = 0;
        for (const r of rows) { if (r.t === "section" || r.t === "subhead") g++; else if (r.t === "line") hasLines[g] = true; }
        let body = ""; g = 0; let cur = 0;
        for (const r of rows) {
            if (r.t === "spacer") { body += `<tr class="r-spacer"><td colspan="4"></td></tr>`; continue; }
            if (r.t === "section" || r.t === "subhead") {
                g++; cur = g;
                const base = r.t === "section" ? "r-section" : "r-subhead";
                const fold = hasLines[g];
                const chev = fold ? `<span class="chev">▸</span>` : "";
                body += `<tr class="${base}${fold ? " r-fold" : ""}" data-g="${g}"><td class="lbl" colspan="4">${chev}${this._esc(r.l)}</td></tr>`;
                continue;
            }
            const p = this.pct(r.c, r.p);
            const cls = r.t === "line" ? "r-line" : r.t === "sub" ? "r-sub" : r.t === "total" ? "r-total" : "r-grand";
            const showPct = r.t !== "line";
            const drill = (r.t === "line" && r.a && r.a.length) ? ` drill" data-acc="${r.a.join(",")}` : "";
            const extra = r.t === "line" ? ` foldable g${cur}` : "";
            body += `<tr class="${cls}${extra}${drill}">
                <td class="lbl">${this._esc(r.l)}</td>
                <td class="amt">${this.fmt(r.c)}</td>
                <td class="amt">${this.fmt(r.p)}</td>
                <td class="amt"><span class="pct ${showPct ? p.c : "mut"}">${showPct ? p.t : ""}</span></td>
            </tr>`;
        }
        const titles = { pl: "Statement of Profit & Loss", bs: "Statement of Financial Position", tb: "Trial Balance" };
        const curFy = this.fyLabel(this.meta.date_from, this.meta.date_to);
        const priFy = this.fyLabel(this.shiftYear(this.meta.date_from), this.shiftYear(this.meta.date_to));
        const period = this.report === "pl"
            ? `For the year ended ${this.fmtDate(this.meta.date_to)}`
            : `As at ${this.fmtDate(this.meta.date_to)}`;
        const head = this.report === "tb"
            ? `<tr><th class="lft">Account</th><th>Debit</th><th>Credit</th><th></th></tr>`
            : `<tr><th class="lft"></th><th>${this._esc(curFy)}</th><th>${this._esc(priFy)}</th><th>Δ %</th></tr>`;
        const tilesHtml = (tiles && tiles.length) ? `<div class="fs-tiles">${tiles.map((t) => `
            <div class="fs-tile ${t.kind || ""}">
              <div class="fs-tile-lab">${this._esc(t.lab)}</div>
              <div class="fs-tile-val"><span class="fs-cur">${this._esc(this.cur)} </span>${this.fmt(t.val)}</div>
              <div class="fs-tile-sub">${this._esc(t.sub || "")}</div>
            </div>`).join("")}</div>` : "";
        this.q("view").innerHTML = tilesHtml + `<div class="fs-stmt">
            <div class="fs-stmt-head"><div class="fs-stmt-title">${titles[this.report] || ""}</div>
              <div class="fs-stmt-meta">${period} · all figures in ${this._esc(this.cur)}</div></div>
            <div class="fs-scroll"><table>
              <thead>${head}</thead><tbody>${body}</tbody></table></div></div>`;
    }

    _renderAged(res) {
        const block = (title, data) => {
            let body = "", tot = [0, 0, 0, 0];
            for (const row of data) {
                row.b.forEach((v, i) => tot[i] += v);
                const sum = row.b.reduce((a, x) => a + x, 0);
                const bar = row.b.map((v, i) => v ? `<i style="width:${(v / sum * 100).toFixed(1)}%;background:${AGED_COLORS[i]}"></i>` : "").join("");
                body += `<tr class="r-line"><td class="lbl" style="padding-left:26px">${this._esc(row.nm)}</td>
                  ${row.b.map((v) => `<td class="amt">${this.fmt(v)}</td>`).join("")}
                  <td class="amt" style="font-weight:700;color:var(--fs-ink)">${this.fmt(sum)}</td>
                  <td><span class="fs-aged-bar">${bar}</span></td></tr>`;
            }
            const g = tot.reduce((a, x) => a + x, 0);
            body += `<tr class="r-total"><td class="lbl">Total</td>${tot.map((v) => `<td class="amt">${this.fmt(v)}</td>`).join("")}<td class="amt">${this.fmt(g)}</td><td></td></tr>`;
            return `<div class="fs-stmt"><div class="fs-stmt-head"><div class="fs-stmt-title">${title}</div>
              <div class="fs-stmt-meta">As at ${this.meta.date_to} · ${this._esc(this.cur)}</div></div>
              <div class="fs-lgnd">${AGED_LABELS.map((l, i) => `<span><span class="fs-sw" style="background:${AGED_COLORS[i]}"></span>${l}</span>`).join("")}</div>
              <div class="fs-scroll"><table><thead><tr><th class="lft">Partner</th><th>Current</th><th>1–30</th><th>31–60</th><th>60+</th><th>Total</th><th></th></tr></thead>
              <tbody>${body}</tbody></table></div></div>`;
        };
        const empty = `<div class="fs-loading">No open items.</div>`;
        this.q("view").innerHTML =
            (res.ar && res.ar.length ? block("Aged Receivables — Clients", res.ar) : "") +
            (res.ap && res.ap.length ? block("Aged Payables — Vendors", res.ap) : "") ||
            empty;
    }

    _group(g, collapsed) {
        this.root.querySelectorAll(`[data-el="view"] tr.g${g}`).forEach((r) => r.style.display = collapsed ? "none" : "");
    }
    _toggleAll() {
        this.allCollapsed = !this.allCollapsed;
        this.root.querySelectorAll(`[data-el="view"] tr.r-fold`).forEach((h) => {
            h.classList.toggle("r-collapsed", this.allCollapsed);
            this._group(h.dataset.g, this.allCollapsed);
        });
        this.q("fold").textContent = this.allCollapsed ? "⇕ Expand all" : "⇕ Collapse all";
    }

    async _drill(accountIds) {
        try {
            const act = await rpc("/mumtaz_financial_reports/drill", {
                account_ids: accountIds,
                date_from: this.q("from").value || undefined,
                date_to: this.q("to").value || undefined,
            });
            this.action.doAction(act);
        } catch { /* ignore */ }
    }

    _esc(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g,
            (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    }
}

registry.category("actions").add("mumtaz_financial_reports", FinancialStatements);
