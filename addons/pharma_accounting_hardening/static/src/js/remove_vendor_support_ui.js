/** @odoo-module **/
// Removes the third-party vendor's support button from the web client.
//
// cybrosys_support_client cannot be uninstalled (base_accounting_kit and base_account_budget depend on it),
// so its two UI entry points are taken out of the registries instead:
//   - the headset icon in the top bar (also carries the Alt+Shift+H hotkey), and
//   - the "Contact Cybrosys Support" item in the user menu.
// The side-effect imports make sure the vendor files have registered themselves before we remove them,
// whatever order the asset bundle lists the files in.
import "@cybrosys_support_client/js/client_support_systray";
import "@cybrosys_support_client/js/client_support_user_menu";
import { registry } from "@web/core/registry";

const REMOVALS = [
    ["systray", "cybrosys_support_client.ClientSupportSystray"],
    ["user_menuitems", "cybrosys_support"],
];
for (const [category, key] of REMOVALS) {
    const cat = registry.category(category);
    if (cat.contains(key)) {
        cat.remove(key);
    }
}
