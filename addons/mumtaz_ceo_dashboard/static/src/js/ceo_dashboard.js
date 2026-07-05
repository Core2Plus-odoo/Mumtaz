/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/* ------------------------------------------------------------------ *
 * Mumtaz CEO Dashboard — Media Buying
 * Standalone OWL client action. Self-contained: builds its own markup
 * imperatively inside a single root <div>, so OWL never patches the
 * charts. Ships with illustrative sample data for design sign-off.
 * ------------------------------------------------------------------ */

const SHELL = `
  <header class="cd-topbar">
    <div class="cd-topbar-in">
      <div class="cd-brand">
        <div class="cd-brand-mark">IG2</div>
        <div>
          <div class="cd-brand-name">IG2 Media Group</div>
          <div class="cd-brand-sub">CEO Executive Dashboard · Media Buying</div>
        </div>
      </div>
      <div class="cd-spacer"></div>
      <div class="cd-segment" role="group" aria-label="Reporting period">
        <button data-period="ytd" aria-pressed="true">YTD 2026</button>
        <button data-period="q2" aria-pressed="false">Q2</button>
        <button data-period="l3m" aria-pressed="false">Last 3M</button>
      </div>
      <div class="cd-asof" data-el="asof">Fiscal Year 2026<br/><strong>as of 05 Jul 2026</strong></div>
      <button class="cd-theme-toggle" data-role="theme" title="Toggle light / dark" aria-label="Toggle light or dark theme"><span class="cd-ico" data-role="theme-ico">☾</span><span data-role="theme-lbl">Dark</span></button>
    </div>
  </header>

  <div class="cd-wrap">
    <div class="cd-kpis" data-el="kpis"></div>

    <div class="cd-eyebrow">Performance</div>
    <div class="cd-grid cd-g-2-1">
      <div class="cd-card">
        <div class="cd-card-head">
          <div class="cd-card-title">Gross Media Billings by Channel</div>
          <div class="cd-card-meta" data-el="trendMeta">monthly · PKR millions</div>
        </div>
        <div data-el="trend"></div>
        <div class="cd-legend" data-el="trendLegend"></div>
      </div>
      <div class="cd-card">
        <div class="cd-card-head">
          <div class="cd-card-title">Net Revenue</div>
          <div class="cd-card-meta">commission + fees</div>
        </div>
        <div data-el="revChart"></div>
        <div class="cd-legend"><span><span class="cd-swatch" style="background:var(--cd-rev)"></span><span data-el="revLegend">Net revenue (PKR m)</span></span></div>
      </div>
    </div>

    <div class="cd-eyebrow">Book of Business</div>
    <div class="cd-grid cd-g-3">
      <div class="cd-card">
        <div class="cd-card-head"><div class="cd-card-title">Top Clients</div><div class="cd-card-meta">YTD billings</div></div>
        <div class="cd-hbars" data-el="clients"></div>
      </div>
      <div class="cd-card">
        <div class="cd-card-head"><div class="cd-card-title">Budget Pacing</div><div class="cd-card-meta">spent vs planned</div></div>
        <div class="cd-pace" data-el="pacing"></div>
        <div class="cd-legend" style="margin-top:16px">
          <span><span class="cd-swatch" style="background:var(--cd-accent)"></span>Spent</span>
          <span><span class="cd-swatch" style="background:var(--cd-accent-soft)"></span>Planned</span>
          <span><span class="cd-swatch" style="background:var(--cd-ink);opacity:.55"></span>Even pace (today)</span>
        </div>
      </div>
      <div class="cd-card">
        <div class="cd-card-head"><div class="cd-card-title">Top Media Vendors</div><div class="cd-card-meta">YTD spend</div></div>
        <div class="cd-hbars" data-el="vendors"></div>
      </div>
    </div>

    <div class="cd-eyebrow">Active Campaigns</div>
    <div class="cd-card">
      <div class="cd-card-head">
        <div class="cd-card-title">Campaign Watchlist</div>
        <div class="cd-card-meta" data-el="campMeta"></div>
      </div>
      <div class="cd-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Campaign</th><th>Channels</th>
              <th class="num">Budget</th><th class="num">Spent</th>
              <th>Pacing</th><th class="num">Margin</th><th>Status</th>
            </tr>
          </thead>
          <tbody data-el="campBody"></tbody>
        </table>
      </div>
    </div>

    <div class="cd-eyebrow">Cash &amp; Collections</div>
    <div class="cd-card">
      <div class="cd-ar">
        <div>
          <div class="cd-card-title" style="margin-bottom:12px">Accounts Receivable Ageing</div>
          <div class="cd-ar-bar" data-el="arBar"></div>
          <div class="cd-ar-legend" data-el="arLegend"></div>
        </div>
        <div class="cd-ar-stat">
          <div class="cd-lbl">Outstanding</div>
          <div class="cd-big" data-el="arTotal"></div>
          <div class="cd-kpi-foot" style="justify-content:flex-end"><span class="cd-kpi-note" data-el="arNote">DSO 47 days · vendor payables PKR 268m</span></div>
        </div>
      </div>
    </div>

    <div class="cd-foot-note">
      <span class="cd-badge-demo" data-el="badge">Sample data</span>
      <span data-el="footNote">Illustrative figures. Install the Media Buying app and approve a media plan — this dashboard then switches to live data automatically.</span>
    </div>
  </div>

  <div data-el="tip" class="cd-tip" role="tooltip"></div>
`;

class CeoDashboard extends Component {
    static template = "mumtaz_ceo_dashboard.Dashboard";

    setup() {
        this.rootRef = useRef("root");
        onMounted(async () => {
            const host = this.rootRef.el;
            if (!host) return;
            // Live feed served by mumtaz_media_buying when installed and
            // populated; on any failure the built-in sample data renders.
            let live = null;
            try {
                const res = await rpc("/mumtaz_ceo_dashboard/data", {});
                if (res && res.live) live = res;
            } catch {
                live = null;
            }
            host.innerHTML = SHELL;
            this._init(host, live);
        });
    }

    _init(root, live) {
        const $ = (s) => root.querySelector(s);
        const $$ = (s) => root.querySelectorAll(s);
        const q = (name) => root.querySelector('[data-el="' + name + '"]');
        const NS = "http://www.w3.org/2000/svg";
        const el = (t, a) => { const e = document.createElementNS(NS, t); for (const k in (a || {})) e.setAttribute(k, a[k]); return e; };
        const money = (v) => v >= 1000 ? (v / 1000).toFixed(2) + "B" : (Math.round(v * 10) / 10) + "m";
        const CH = ["tv", "digital", "print", "ooh"];
        const CH_LABEL = { tv: "TV & Radio", digital: "Digital & Social", print: "Print", ooh: "Outdoor (OOH)" };
        const CH_VAR = { tv: "--cd-ch-tv", digital: "--cd-ch-digital", print: "--cd-ch-print", ooh: "--cd-ch-ooh" };
        const cvar = (n) => getComputedStyle(root).getPropertyValue(n).trim();

        // ---------------- DATA (live payload, else sample) --------------
        const CUR = (live && live.currency) || "PKR";
        const months = live ? live.months
            : ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"];
        const billings = live ? live.billings : {
            tv: [114, 120, 138, 132, 154, 164, 24],
            digital: [72, 76, 87, 84, 97, 103, 15],
            print: [35, 37, 42, 40, 47, 50, 7],
            ooh: [27, 29, 34, 32, 36, 39, 5],
        };
        const revenue = live ? live.revenue
            : [28.5, 30.1, 35.2, 33.0, 39.4, 42.8, 5.9];
        const sampleClients = [
            { nm: "Unilever Pakistan", v: 286 }, { nm: "Telenor", v: 231 },
            { nm: "Bank Alfalah", v: 188 }, { nm: "Coca-Cola", v: 164 },
            { nm: "K&N's Foods", v: 132 }, { nm: "Bata Pakistan", v: 98 },
        ];
        const clients = live ? live.clients : sampleClients;
        const vendors = live ? live.vendors : [
            { nm: "GEO Network", v: 214 }, { nm: "ARY Digital", v: 176 },
            { nm: "Hum Network", v: 142 }, { nm: "Meta", v: 138 },
            { nm: "Google / YT", v: 121 }, { nm: "Dawn Media", v: 88 },
        ];
        const pacing = (live && live.pacing.length) ? live.pacing : [
            { nm: "TV & Radio", ch: "tv", plan: 520, spent: 398 },
            { nm: "Digital", ch: "digital", plan: 330, spent: 271 },
            { nm: "Print", ch: "print", plan: 172, spent: 118 },
            { nm: "OOH", ch: "ooh", plan: 130, spent: 126 },
        ];
        const campaigns = live ? live.campaigns : [
            { nm: "Summer Refresh 2026", cl: "Unilever", ch: ["tv", "digital"], budget: 120, spent: 88, margin: 12.4, status: "good", label: "On track" },
            { nm: "5G Nationwide Launch", cl: "Telenor", ch: ["tv", "ooh", "digital"], budget: 180, spent: 152, margin: 10.8, status: "good", label: "On track" },
            { nm: "Ramadan Banking", cl: "Bank Alfalah", ch: ["tv", "print"], budget: 95, spent: 96, margin: 9.6, status: "serious", label: "Overpacing" },
            { nm: "Zero Sugar", cl: "Coca-Cola", ch: ["digital", "ooh"], budget: 72, spent: 41, margin: 13.2, status: "warning", label: "Underpacing" },
            { nm: "Eid Feast", cl: "K&N's", ch: ["tv"], budget: 64, spent: 60, margin: 11.9, status: "good", label: "On track" },
            { nm: "Back to School", cl: "Bata", ch: ["print", "digital"], budget: 38, spent: 12, margin: 14.1, status: "warning", label: "At risk" },
            { nm: "Monsoon Drive", cl: "Suzuki", ch: ["tv", "ooh"], budget: 88, spent: 79, margin: 10.2, status: "good", label: "On track" },
            { nm: "Wallet Everywhere", cl: "Easypaisa", ch: ["digital"], budget: 56, spent: 58, margin: 8.9, status: "serious", label: "Overpacing" },
        ];
        const ageing = live ? live.ageing : [
            { nm: "Current", v: 178, c: "--cd-good" },
            { nm: "1–30 days", v: 84, c: "--cd-ch-tv" },
            { nm: "31–60 days", v: 32, c: "--cd-warning" },
            { nm: "60+ days", v: 18, c: "--cd-critical" },
        ];
        // headline numbers not derivable from the chart arrays
        const K = live ? live.kpis : {
            active_campaigns: 28, clients_live: 34,
            receivables: 312, payables: 268, dso: 47,
        };
        const asOf = live && live.as_of
            ? new Date(live.as_of + "T00:00:00")
            : new Date(2026, 6, 5);
        const yr = asOf.getFullYear();
        const asOfLabel = asOf.toLocaleDateString("en-GB",
            { day: "2-digit", month: "short", year: "numeric" });
        const nM = months.length;
        const PERIODS = {
            ytd: [0, nM],
            q2: [Math.min(3, nM - 1), Math.min(6, nM)],
            l3m: [Math.max(0, nM - 3), nM],
        };
        let period = "ytd";

        // contextual chrome: as-of stamp, currency labels, live/sample badge
        q("asof").innerHTML =
            `Fiscal Year ${yr}<br><strong>as of ${asOfLabel}</strong>`;
        q("revLegend").textContent = `Net revenue (${CUR} m)`;
        if (live) {
            q("badge").textContent = "Live data";
            q("footNote").innerHTML =
                `Figures computed from approved & running media plans, ` +
                `vendor bills and client invoices in <strong>${live.db}</strong>.`;
        }

        // ---------------- tooltip ----------------
        const tip = q("tip");
        const showTip = (html, x, y) => {
            tip.innerHTML = html; tip.style.opacity = 1;
            const r = tip.getBoundingClientRect();
            let nx = x + 14, ny = y - r.height - 10;
            if (nx + r.width > window.innerWidth - 8) nx = x - r.width - 14;
            if (ny < 8) ny = y + 16;
            tip.style.left = nx + "px"; tip.style.top = ny + "px";
        };
        const hideTip = () => { tip.style.opacity = 0; };

        // ---------------- KPIs ----------------
        const sumRange = (arr, r) => { let s = 0; for (let i = r[0]; i < r[1]; i++) s += arr[i]; return s; };
        function renderKPIs() {
            const r = PERIODS[period];
            const totalBill = CH.reduce((a, c) => a + sumRange(billings[c], r), 0);
            const totalRev = sumRange(revenue, r);
            const margin = totalBill ? totalRev / totalBill * 100 : 0;
            // sample mode shows illustrative deltas; live mode shows a
            // neutral "live" chip (no fabricated year-on-year comparisons)
            const dl = (sample) => live
                ? { delta: "live", dir: "flat" } : sample;
            const data = [
                { cls: "", label: "Gross Media Billings", val: money(totalBill), pkr: true, note: live ? "approved + running plans" : "vs FY25", ...dl({ delta: "+18.4%", dir: "up" }) },
                { cls: "k-rev", label: "Net Revenue", val: money(totalRev), pkr: true, note: "commission + fees", ...dl({ delta: "+21.2%", dir: "up" }) },
                { cls: "k-margin", label: "Blended Margin", val: margin.toFixed(1) + "%", pkr: false, note: live ? "of client billings" : "target 11.0%", ...dl({ delta: "+0.6 pp", dir: "up" }) },
                { cls: "k-camp", label: "Active Campaigns", val: String(K.active_campaigns), pkr: false, note: `${K.clients_live} clients live`, ...dl({ delta: "+5", dir: "up" }) },
                { cls: "k-cash", label: "Receivables", val: money(K.receivables), pkr: true, delta: `DSO ${K.dso}d`, dir: "flat", note: `payables ${money(K.payables)}` },
            ];
            q("kpis").innerHTML = data.map((d) => `
                <div class="cd-kpi ${d.cls}">
                    <div class="cd-kpi-label">${d.label}</div>
                    <div class="cd-kpi-value">${d.pkr ? `<span class="cd-cur">${CUR} </span>` : ''}${d.val}</div>
                    <div class="cd-kpi-foot">
                        <span class="cd-delta ${d.dir}">${d.dir === 'up' ? '▲' : d.dir === 'down' ? '▼' : '●'} ${d.delta}</span>
                        <span class="cd-kpi-note">${d.note}</span>
                    </div>
                </div>`).join("");
        }

        // ---------------- stacked billings ----------------
        function renderTrend() {
            const host = q("trend"); host.innerHTML = "";
            const r = PERIODS[period];
            const idx = []; for (let i = r[0]; i < r[1]; i++) idx.push(i);
            const W = 680, H = 280, padL = 38, padR = 14, padT = 26, padB = 28;
            const iw = W - padL - padR, ih = H - padT - padB;
            const totals = idx.map((i) => CH.reduce((a, c) => a + billings[c][i], 0));
            const maxV = Math.max(...totals) * 1.12;
            const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Monthly gross billings by channel" });
            const ticks = 4;
            for (let t = 0; t <= ticks; t++) {
                const val = maxV * t / ticks, y = padT + ih - (val / maxV) * ih;
                svg.appendChild(el("line", { x1: padL, x2: W - padR, y1: y, y2: y, stroke: cvar('--cd-grid'), "stroke-width": 1 }));
                const tx = el("text", { x: padL - 8, y: y + 3, class: "cd-tick", "text-anchor": "end" }); tx.textContent = Math.round(val); svg.appendChild(tx);
            }
            const n = idx.length;
            const bw = Math.min(58, iw / n * 0.62);
            const step = iw / n;
            idx.forEach((mi, k) => {
                const cx = padL + step * k + step / 2;
                let acc = 0;
                CH.forEach((c) => {
                    const v = billings[c][mi]; if (v <= 0) return;
                    const h = (v / maxV) * ih;
                    const y = padT + ih - acc - h;
                    const rct = el("rect", { x: cx - bw / 2, y: y, width: bw, height: Math.max(h - 2, 0), rx: 2, fill: cvar(CH_VAR[c]), class: "cd-seg" });
                    rct.addEventListener("mousemove", (e) => {
                        const tot = CH.reduce((a, cc) => a + billings[cc][mi], 0);
                        showTip(`<div class="cd-tt-h">${months[mi]} ${yr} · ${CUR} ${Math.round(tot)} m</div>` +
                            CH.map((cc) => `<div class="cd-tt-r"><span class="k"><span class="cd-tt-dot" style="background:${cvar(CH_VAR[cc])}"></span>${CH_LABEL[cc]}</span><span class="v">${billings[cc][mi]}</span></div>`).join(""),
                            e.clientX, e.clientY);
                    });
                    rct.addEventListener("mouseleave", hideTip);
                    acc += h; svg.appendChild(rct);
                });
                const tl = el("text", { x: cx, y: padT + ih - acc - 7, class: "cd-bar-total", "text-anchor": "middle" });
                tl.textContent = Math.round(CH.reduce((a, c) => a + billings[c][mi], 0)); svg.appendChild(tl);
                const xl = el("text", { x: cx, y: H - 9, class: "cd-axis-label", "text-anchor": "middle" }); xl.textContent = months[mi]; svg.appendChild(xl);
            });
            svg.appendChild(el("line", { x1: padL, x2: W - padR, y1: padT + ih, y2: padT + ih, stroke: cvar('--cd-baseline'), "stroke-width": 1 }));
            host.appendChild(svg);
            q("trendLegend").innerHTML = CH.map((c) => `<span><span class="cd-swatch" style="background:${cvar(CH_VAR[c])}"></span>${CH_LABEL[c]}</span>`).join("");
            q("trendMeta").textContent = `${months[idx[0]]}–${months[idx[idx.length - 1]]} ${yr} · ${CUR} millions`;
        }

        // ---------------- revenue area ----------------
        function renderRev() {
            const host = q("revChart"); host.innerHTML = "";
            const r = PERIODS[period];
            const idx = []; for (let i = r[0]; i < r[1]; i++) idx.push(i);
            const vals = idx.map((i) => revenue[i]);
            const W = 320, H = 280, padL = 34, padR = 14, padT = 22, padB = 28;
            const iw = W - padL - padR, ih = H - padT - padB;
            const maxV = Math.max(...vals) * 1.18, minV = 0;
            const x = (k) => padL + (idx.length === 1 ? iw / 2 : iw * k / (idx.length - 1));
            const y = (v) => padT + ih - ((v - minV) / (maxV - minV)) * ih;
            const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Net revenue trend" });
            const ticks = 4;
            for (let t = 0; t <= ticks; t++) {
                const val = maxV * t / ticks, yy = padT + ih - (val / maxV) * ih;
                svg.appendChild(el("line", { x1: padL, x2: W - padR, y1: yy, y2: yy, stroke: cvar('--cd-grid'), "stroke-width": 1 }));
                const tx = el("text", { x: padL - 8, y: yy + 3, class: "cd-tick", "text-anchor": "end" }); tx.textContent = Math.round(val); svg.appendChild(tx);
            }
            const dLine = vals.map((v, k) => `${k ? 'L' : 'M'}${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
            const dArea = dLine + ` L${x(vals.length - 1)},${padT + ih} L${x(0)},${padT + ih} Z`;
            const gid = "cd-revg";
            const grad = el("linearGradient", { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 });
            grad.appendChild(el("stop", { offset: "0%", "stop-color": cvar('--cd-rev'), "stop-opacity": .28 }));
            grad.appendChild(el("stop", { offset: "100%", "stop-color": cvar('--cd-rev'), "stop-opacity": 0 }));
            svg.appendChild(grad);
            svg.appendChild(el("path", { d: dArea, fill: `url(#${gid})` }));
            svg.appendChild(el("path", { d: dLine, fill: "none", stroke: cvar('--cd-rev'), "stroke-width": 2.4, "stroke-linejoin": "round", "stroke-linecap": "round" }));
            vals.forEach((v, k) => {
                const isEnd = k === vals.length - 1;
                const dot = el("circle", { cx: x(k), cy: y(v), r: isEnd ? 4.5 : 3.4, fill: cvar('--cd-surface'), stroke: cvar('--cd-rev'), "stroke-width": 2.2 });
                const hit = el("circle", { cx: x(k), cy: y(v), r: 14, fill: "transparent" });
                hit.addEventListener("mousemove", (e) => showTip(`<div class="cd-tt-h">${months[idx[k]]} ${yr}</div><div class="cd-tt-r"><span class="k">Net revenue</span><span class="v">${CUR} ${v} m</span></div>`, e.clientX, e.clientY));
                hit.addEventListener("mouseleave", hideTip);
                svg.appendChild(dot); svg.appendChild(hit);
                if (isEnd) { const t = el("text", { x: x(k), y: y(v) - 10, class: "cd-bar-total", "text-anchor": "end" }); t.textContent = v; svg.appendChild(t); }
                const xl = el("text", { x: x(k), y: H - 9, class: "cd-axis-label", "text-anchor": "middle" }); xl.textContent = months[idx[k]]; svg.appendChild(xl);
            });
            host.appendChild(svg);
        }

        // ---------------- horizontal bars ----------------
        function renderHBars(name, rows, colorVar) {
            const max = Math.max(...rows.map((r) => r.v));
            q(name).innerHTML = rows.map((r) => `
                <div class="cd-hbar">
                    <span class="cd-nm" title="${r.nm}">${r.nm}</span>
                    <span class="cd-track"><span class="cd-fill" style="width:${(r.v / max * 100).toFixed(1)}%;background:${cvar(colorVar)}"></span></span>
                    <span class="cd-val">${r.v}m</span>
                </div>`).join("");
        }

        // ---------------- pacing ----------------
        function renderPacing() {
            const evenPace = 54;
            const maxPlan = Math.max(...pacing.map((x) => x.plan));
            q("pacing").innerHTML = pacing.map((p) => {
                const pct = p.spent / p.plan * 100;
                const planW = p.plan / maxPlan * 100;
                const spentW = p.spent / maxPlan * 100;
                const st = pct > 100 ? 'critical' : pct >= evenPace - 6 ? 'good' : 'warning';
                const stc = st === 'critical' ? '--cd-critical' : st === 'good' ? '--cd-good' : '--cd-warning';
                return `<div class="cd-pace-row">
                    <span class="cd-pace-nm"><span class="cd-swatch" style="background:${cvar(CH_VAR[p.ch])}"></span>${p.nm}</span>
                    <span class="cd-pace-track">
                        <span class="cd-pace-plan" style="width:${planW}%"></span>
                        <span class="cd-pace-spent" style="width:${spentW}%"></span>
                        <span class="cd-pace-target" style="left:${planW * evenPace / 100}%"></span>
                    </span>
                    <span class="cd-pace-pct" style="color:${cvar(stc)}">${Math.round(pct)}%</span>
                </div>`;
            }).join("");
        }

        // ---------------- campaigns ----------------
        function renderCampaigns() {
            q("campBody").innerHTML = campaigns.map((c) => {
                const pace = c.spent / c.budget * 100;
                const pc = pace > 100 ? '--cd-critical' : pace >= 45 ? '--cd-accent' : '--cd-warning';
                return `<tr>
                    <td><div class="cd-camp-nm">${c.nm}</div><div class="cd-camp-cl">${c.cl}</div></td>
                    <td><span class="cd-chips">${c.ch.map((x) => `<span class="cd-chip ${x}">${x === 'tv' ? 'TV/Radio' : x === 'ooh' ? 'OOH' : x[0].toUpperCase() + x.slice(1)}</span>`).join("")}</span></td>
                    <td class="num">${c.budget}m</td>
                    <td class="num">${c.spent}m</td>
                    <td><span class="cd-mini"><i style="width:${Math.min(pace, 100)}%;background:${cvar(pc)}"></i></span> <span style="font-size:11.5px;color:var(--cd-muted);font-variant-numeric:tabular-nums">${Math.round(pace)}%</span></td>
                    <td class="num" style="font-weight:700">${c.margin}%</td>
                    <td><span class="cd-pill ${c.status === 'good' ? 'good' : c.status}">${c.label}</span></td>
                </tr>`;
            }).join("");
            q("campMeta").textContent = live
                ? `${campaigns.length} active plan${campaigns.length === 1 ? "" : "s"} · sorted by size`
                : `${campaigns.length} of 28 flagged · sorted by attention`;
        }

        // ---------------- receivables ----------------
        function renderAR() {
            const total = ageing.reduce((a, x) => a + x.v, 0);
            q("arBar").innerHTML = ageing.map((a) => `<i style="width:${a.v / total * 100}%;background:${cvar(a.c)}" title="${a.nm}: ${CUR} ${a.v}m"></i>`).join("");
            q("arLegend").innerHTML = ageing.map((a) => `<span><span class="cd-swatch" style="background:${cvar(a.c)}"></span>${a.nm} · <strong style="color:var(--cd-ink)">${a.v}m</strong></span>`).join("");
            q("arTotal").innerHTML = `<span style="font-size:14px;color:var(--cd-ink-2);font-weight:650">${CUR} </span>${money(total)}`;
            q("arNote").textContent = `DSO ${K.dso} days · vendor payables ${CUR} ${money(K.payables)}`;
        }

        function renderAll() {
            renderKPIs(); renderTrend(); renderRev();
            renderHBars("clients", clients, "--cd-accent");
            renderHBars("vendors", vendors, "--cd-ch-tv");
            renderPacing(); renderCampaigns(); renderAR();
        }
        renderAll();

        // ---------------- period toggle ----------------
        $$('.cd-segment button').forEach((b) => {
            b.addEventListener("click", () => {
                period = b.dataset.period;
                $$('.cd-segment button').forEach((x) => x.setAttribute("aria-pressed", x === b));
                renderKPIs(); renderTrend(); renderRev();
            });
        });

        // ---------------- theme toggle (default light) ----------------
        const themeBtn = root.querySelector('[data-role="theme"]');
        const syncThemeBtn = () => {
            const dark = root.getAttribute("data-theme") === "dark";
            root.querySelector('[data-role="theme-ico"]').textContent = dark ? "☀" : "☾";
            root.querySelector('[data-role="theme-lbl"]').textContent = dark ? "Light" : "Dark";
        };
        syncThemeBtn();
        themeBtn.addEventListener("click", () => {
            root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
            syncThemeBtn(); renderAll();
        });
    }
}

registry.category("actions").add("mumtaz_ceo_dashboard", CeoDashboard);
