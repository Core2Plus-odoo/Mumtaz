/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// The order the page reads in. Work you are late on comes before work you are
// not, and the things nobody can act on (blocked, in review) come last.
const SECTION_ORDER = [
    "overdue", "today", "due_soon", "stale",
    "blocked", "in_review", "no_deadline", "recently_assigned",
];

export class C2pWorkHub extends Component {
    static template = "c2p_work_hub.WorkHub";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            data: null,
            loading: true,
            error: null,
            // id of the task whose update panel is open; only ever one
            openTask: null,
            draft: { progress: "", next_action: "", blocker: "", state: "" },
            saving: false,
        });
        onWillStart(() => this.load());
    }

    get sections() {
        const d = this.state.data;
        if (!d) {
            return [];
        }
        return SECTION_ORDER.map((key) => [key, d[key]]).filter(
            ([, section]) => section && section.count
        );
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("c2p.work.hub", "get_data", []);
        } catch (err) {
            // A failed load must say so rather than render an empty page that
            // reads as "you have no work".
            this.state.error = err.message?.data?.message || err.message || String(err);
        } finally {
            this.state.loading = false;
        }
    }

    openSection(section) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: section.label,
            res_model: section.action.res_model,
            domain: section.action.domain,
            views: [[false, "list"], [false, "form"]],
        });
    }

    openTaskForm(taskId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: taskId,
            views: [[false, "form"]],
        });
    }

    togglePanel(taskId) {
        if (this.state.openTask === taskId) {
            this.state.openTask = null;
            return;
        }
        this.state.openTask = taskId;
        this.state.draft = { progress: "", next_action: "", blocker: "", state: "" };
    }

    async submitUpdate(taskId) {
        const draft = this.state.draft;
        const payload = {};
        for (const key of ["progress", "next_action", "blocker", "state"]) {
            if (draft[key]) {
                payload[key] = draft[key];
            }
        }
        if (!Object.keys(payload).length) {
            this.notification.add(
                _t("Add progress, a next action, a blocker or a status first."),
                { type: "warning" }
            );
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("project.task", "action_c2p_quick_update", [
                [taskId], payload,
            ]);
            this.notification.add(_t("Update saved."), { type: "success" });
            this.state.openTask = null;
            await this.load();
        } catch (err) {
            // Server-side validation (a blocker the tracker requires, a stage
            // that needs a milestone) surfaces here verbatim: the user needs
            // the real reason, not a generic failure.
            this.notification.add(
                err.message?.data?.message || _t("Could not save the update."),
                { type: "danger", sticky: true }
            );
        } finally {
            this.state.saving = false;
        }
    }

    async submitForReview(taskId) {
        try {
            await this.orm.call("project.task", "action_c2p_submit_for_review", [[taskId]]);
            this.notification.add(_t("Submitted for review."), { type: "success" });
            await this.load();
        } catch (err) {
            this.notification.add(
                err.message?.data?.message || _t("Could not submit for review."),
                { type: "danger", sticky: true }
            );
        }
    }

    priorityLabel(priority) {
        return priority === "1" ? _t("Important") : "";
    }
}

registry.category("actions").add("c2p_work_hub", C2pWorkHub);
