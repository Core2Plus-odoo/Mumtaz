/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Delivery dashboard — the C2P Solutions lead's view.
 *
 * Carries no commercial figure anywhere, by construction: `delivery_data()`
 * returns none, so there is nothing here to leak.
 */
export class C2pDeliveryDashboard extends Component {
    static template = "c2p_project_tracker.DeliveryDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: null, data: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("c2p.dashboard", "delivery_data", []);
        } catch (error) {
            this.state.error = error.data?.message || error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    /** Bar widths as a share of the busiest person, so the comparison is fair. */
    get load() {
        const rows = this.state.data?.team_load || [];
        const max = Math.max(1, ...rows.map((r) => r.open));
        return rows.map((r) => ({
            ...r,
            openPct: ((r.open - r.overdue) / max) * 100,
            overduePct: (r.overdue / max) * 100,
            hours: Math.round(r.hours),
        }));
    }

    openDomain(domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "project.task",
            domain: domain,
            views: [[false, "list"], [false, "form"]],
        });
    }

    openHygiene(entry) {
        this.openDomain(entry.domain, entry.label);
    }
}

registry.category("actions").add("c2p_delivery_dashboard", C2pDeliveryDashboard);
