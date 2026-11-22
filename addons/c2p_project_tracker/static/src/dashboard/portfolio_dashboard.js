/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Geometry for the SVG roadmap. Kept here rather than in CSS because the
// layout maths needs the numbers.
const LANE_H = 34;
const LANE_PAD = 10;
const AXIS_H = 26;
const LEFT_W = 190;
const RIGHT_PAD = 24;
const VIEW_W = 1000;

/**
 * Portfolio dashboard — the Managing Partner's view.
 *
 * Charts are inline SVG rather than Chart.js: the asset path for Odoo's
 * bundled copy moves between versions, and a wrong path takes the whole
 * dashboard down. Nothing here needs a charting library.
 */
export class C2pPortfolioDashboard extends Component {
    static template = "c2p_project_tracker.PortfolioDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            expanded: {},
            filters: { rag: null, engagement_type: null, account_manager_id: null },
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "c2p.dashboard", "portfolio_data", [],
                {
                    rag_filter: this.state.filters.rag || null,
                    engagement_type: this.state.filters.engagement_type || null,
                    account_manager_id: this.state.filters.account_manager_id || null,
                }
            );
        } catch (error) {
            // Surface the reason rather than an empty page: the most likely
            // cause is a group the user does not have.
            this.state.error = error.data?.message || error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    // ── Filters ──────────────────────────────────────────────────────────
    async setFilter(key, value) {
        this.state.filters[key] = value === "" ? null : value;
        await this.load();
    }

    async clearFilters() {
        this.state.filters = { rag: null, engagement_type: null, account_manager_id: null };
        await this.load();
    }

    get hasFilters() {
        return Object.values(this.state.filters).some((v) => v);
    }

    // ── Formatting ───────────────────────────────────────────────────────
    money(value) {
        if (value === undefined || value === null) {
            return "—";
        }
        const symbol = this.state.data?.currency || "";
        return `${symbol} ${Math.round(value).toLocaleString()}`;
    }

    ragLabel(rag) {
        return { red: "Red", amber: "Amber", green: "Green", grey: "No data" }[rag] || rag;
    }

    /** Status is never colour alone — every pill carries this glyph and a label. */
    ragGlyph(rag) {
        return { red: "▲", amber: "■", green: "●", grey: "–" }[rag] || "–";
    }

    slippageLabel(days) {
        if (!days) {
            return "on baseline";
        }
        return days > 0 ? `+${days}d late` : `${days}d early`;
    }

    // ── Drill-down ───────────────────────────────────────────────────────
    toggleRow(id) {
        this.state.expanded[id] = !this.state.expanded[id];
    }

    openProject(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.project",
            res_id: id,
            views: [[false, "form"]],
        });
    }

    openKpi(kind) {
        const domains = {
            engagements: [["c2p_layer", "=", "portfolio"]],
            overdue_milestones: [["c2p_layer", "=", "portfolio"],
                                 ["overdue_milestones_count", ">", 0]],
            blockers: [["c2p_layer", "=", "portfolio"], ["open_blockers_count", ">", 0]],
            outstanding: [["c2p_layer", "=", "portfolio"], ["amount_outstanding", ">", 0]],
            payable_to_solutions: [["c2p_layer", "=", "portfolio"],
                                   ["subcontract_outstanding", ">", 0]],
        };
        if (!domains[kind]) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Engagements",
            res_model: "project.project",
            domain: domains[kind],
            views: [[false, "list"], [false, "form"]],
        });
    }

    // ── RAG composition bar ──────────────────────────────────────────────
    get ragSegments() {
        const counts = this.state.data?.rag_counts || {};
        const total = Object.values(counts).reduce((a, b) => a + b, 0);
        if (!total) {
            return [];
        }
        return ["red", "amber", "green", "grey"]
            .filter((key) => counts[key])
            .map((key) => ({
                key,
                label: this.ragLabel(key),
                count: counts[key],
                pct: (counts[key] / total) * 100,
            }));
    }

    // ── Roadmap geometry ─────────────────────────────────────────────────
    get roadmap() {
        const raw = this.state.data?.roadmap;
        if (!raw || !raw.has_dates) {
            return null;
        }
        const start = new Date(raw.start).getTime();
        const end = new Date(raw.end).getTime();
        // A single date would divide by zero; pad to a month either side.
        const span = end > start ? end - start : 1000 * 60 * 60 * 24 * 60;
        const plotW = VIEW_W - LEFT_W - RIGHT_PAD;
        const x = (iso) => {
            if (!iso) {
                return null;
            }
            const t = new Date(iso).getTime();
            return LEFT_W + ((t - start) / span) * plotW;
        };
        const lanes = raw.lanes.map((lane, index) => ({
            ...lane,
            y: AXIS_H + LANE_PAD + index * LANE_H,
            points: lane.milestones.map((m) => ({
                ...m,
                cx: x(m.deadline),
                ghostCx: m.baseline && m.baseline !== m.deadline ? x(m.baseline) : null,
            })),
        }));
        return {
            lanes,
            height: AXIS_H + LANE_PAD * 2 + lanes.length * LANE_H,
            width: VIEW_W,
            todayX: x(raw.today),
            startLabel: raw.start,
            endLabel: raw.end,
            leftW: LEFT_W,
            undatedTotal: raw.lanes.reduce((a, l) => a + l.undated_count, 0),
        };
    }

    // ── Trend charts, as SVG paths ───────────────────────────────────────
    get trends() {
        const raw = this.state.data?.trends;
        if (!raw || !raw.weeks.length) {
            return null;
        }
        const w = 520;
        const h = 120;
        const pad = 22;
        const n = raw.weeks.length;
        const stepX = n > 1 ? (w - pad * 2) / (n - 1) : 0;

        const maxDone = Math.max(1, ...raw.completed);
        const bars = raw.completed.map((value, i) => {
            const barW = Math.max(6, (w - pad * 2) / Math.max(n, 1) - 4);
            const height = (value / maxDone) * (h - pad * 2);
            return {
                week: raw.weeks[i],
                value,
                x: pad + (n > 1 ? i * stepX : (w - pad * 2) / 2) - barW / 2,
                y: h - pad - height,
                width: barW,
                height,
            };
        });

        const slip = raw.slippage;
        const maxSlip = Math.max(1, ...slip.map((v) => Math.abs(v)));
        const points = slip.map((value, i) => ({
            week: raw.weeks[i],
            value,
            x: pad + (n > 1 ? i * stepX : (w - pad * 2) / 2),
            y: h / 2 - (value / maxSlip) * (h / 2 - pad),
        }));

        return {
            w, h, pad,
            bars,
            maxDone,
            slipPath: points.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" "),
            slipPoints: points,
            zeroY: h / 2,
            singleWeek: n === 1,
        };
    }
}

registry.category("actions").add("c2p_portfolio_dashboard", C2pPortfolioDashboard);
