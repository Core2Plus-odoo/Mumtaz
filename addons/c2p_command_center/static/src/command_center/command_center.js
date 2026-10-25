/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const REFRESH_MS = 5 * 60 * 1000;

/**
 * C2P Command Center — one page for everything happening across C2P.
 * All figures come from c2p.command.center.get_data() in a single call;
 * every number and row opens the underlying Odoo records.
 */
export class C2pCommandCenter extends Component {
    static template = "c2p_command_center.CommandCenter";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: null, data: null, actFilter: "open" });
        onWillStart(() => this.fetchData());
        this.timer = setInterval(() => this.fetchData(true), REFRESH_MS);
        onWillUnmount(() => clearInterval(this.timer));
    }

    async fetchData(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("c2p.command.center", "get_data", []);
        } catch (error) {
            this.state.error = error.data?.message || error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    // ── formatting ─────────────────────────────────────────────────────
    money(v) {
        const n = Number(v || 0);
        if (Math.abs(n) >= 1e6) {
            return (n / 1e6).toFixed(1) + "M";
        }
        if (Math.abs(n) >= 1e3) {
            return (n / 1e3).toFixed(n >= 1e5 ? 0 : 1) + "k";
        }
        return n.toFixed(0);
    }
    amount(v) {
        return Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    kpiValue(k) {
        const cur = this.state.data?.pipeline?.currency || "";
        return k.money ? `${cur} ${this.money(k.value)}` : k.value;
    }

    // ── outreach chart ─────────────────────────────────────────────────
    get chart() {
        const series = this.state.data?.outreach?.series || [];
        const max = Math.max(1, ...series.map((s) => s.first + s.followup));
        const w = 100 / Math.max(1, series.length);
        return series.map((s, i) => ({
            ...s,
            x: i * w + w * 0.15,
            width: w * 0.7,
            firstH: (s.first / max) * 100,
            followH: (s.followup / max) * 100,
            total: s.first + s.followup,
        }));
    }

    // ── activities filter ──────────────────────────────────────────────
    get activities() {
        const rows = this.state.data?.activities?.rows || [];
        if (this.state.actFilter === "open") {
            return rows.filter((r) => r.state !== "planned");
        }
        return rows;
    }
    setActFilter(f) {
        this.state.actFilter = f;
    }

    // ── navigation ─────────────────────────────────────────────────────
    openRecord(model, id) {
        if (!model || !id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    openAct(act) {
        if (!act) {
            return;
        }
        const views = act.views === "kanban" ? [[false, "kanban"], [false, "list"], [false, "form"]]
            : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: act.name,
            res_model: act.res_model,
            domain: act.domain,
            views,
            target: "current",
        });
    }
    openBoard() {
        const id = this.state.data?.agents?.board_id;
        if (id) {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "AI Agents · Work Board",
                res_model: "project.task",
                domain: [["project_id", "=", id]],
                context: { default_project_id: id, group_by: "stage_id" },
                views: [[false, "kanban"], [false, "list"], [false, "form"]],
            });
        }
    }
    openProjectTasks(id, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "project.task",
            domain: [["project_id", "=", id]],
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
        });
    }
    openUrl(url) {
        if (url) {
            window.open(url, "_blank");
        }
    }
    scrollTo(section) {
        const el = document.getElementById(`c2p-cc-${section}`);
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }
    stageCount(row, stage) {
        return row.by_stage[stage] || 0;
    }
}

registry.category("actions").add("c2p_command_center", C2pCommandCenter);
