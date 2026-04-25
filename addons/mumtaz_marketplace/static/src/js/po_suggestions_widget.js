/** @odoo-module **/
/*
 * Mumtaz Marketplace — Purchase Order suggestion widget (OWL 3).
 *
 * Embeds inside the purchase.order form view as a smart sidebar that lists
 * up to N alternative marketplace vendors for the items in this PO.
 * Calls purchase.order.get_marketplace_suggestions(limit) on mount.
 */

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class POSuggestionsWidget extends Component {
    static template = "mumtaz_marketplace.POSuggestionsWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading:     true,
            suggestions: [],
            error:       null,
        });

        onWillStart(async () => {
            const recordId = this.props.record.resId;
            if (!recordId) {
                this.state.loading = false;
                return;
            }
            try {
                const suggestions = await this.orm.call(
                    "purchase.order",
                    "get_marketplace_suggestions",
                    [[recordId], 3],
                );
                this.state.suggestions = suggestions || [];
            } catch (err) {
                this.state.error = err?.message?.data?.message || String(err);
            } finally {
                this.state.loading = false;
            }
        });
    }

    openListing(suggestion) {
        this.action.doAction({
            type:      "ir.actions.act_window",
            res_model: "mumtaz.marketplace.listing",
            res_id:    suggestion.id,
            views:     [[false, "form"]],
            target:    "current",
        });
    }

    sendRfq() {
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.notification.add("Save the PO before sending an RFQ.", { type: "warning" });
            return;
        }
        this.action.doActionButton({
            type:        "object",
            name:        "action_marketplace_send_rfq",
            resModel:    "purchase.order",
            resId:       recordId,
            resIds:      [recordId],
        });
    }

    formatPrice(s) {
        if (!s.price) return "—";
        return `${s.currency || ""} ${s.price.toFixed(2)}`;
    }
}

export const poSuggestionsWidget = {
    component: POSuggestionsWidget,
    fieldDependencies: [{ name: "marketplace_alt_count", type: "integer" }],
};

registry.category("fields").add("mumtaz_po_suggestions", poSuggestionsWidget);
