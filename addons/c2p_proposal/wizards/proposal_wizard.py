import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.c2p_proposal.models.sale_order import (
    DOMAINS, DOMAIN_TEXT, classify_domains)

# Industry keyword -> service keywords to recommend (matched against product names).
INDUSTRY_RECO = {
    "manufactur": ["erp", "implementation", "bi", "dashboard", "support"],
    "factory": ["erp", "implementation", "bi", "support"],
    "retail": ["erp", "ecommerce", "e-commerce", "bi", "support"],
    "ecommerce": ["ecommerce", "e-commerce", "erp", "bi"],
    "e-commerce": ["ecommerce", "e-commerce", "erp", "bi"],
    "trading": ["erp", "implementation", "support"],
    "distribution": ["erp", "implementation", "bi", "support"],
    "wholesale": ["erp", "implementation", "bi"],
    "construction": ["erp", "implementation", "support"],
    "contracting": ["erp", "implementation", "support"],
    "services": ["erp", "implementation", "training"],
    "consult": ["erp", "implementation", "training"],
    "finance": ["finance", "vat", "advisory", "erp"],
    "accounting": ["finance", "vat", "advisory"],
    "education": ["erp", "implementation", "support", "training"],
    "school": ["erp", "implementation", "training"],
    "healthcare": ["erp", "implementation", "support"],
    "hospital": ["erp", "implementation", "support"],
    "clinic": ["erp", "implementation", "support"],
    "logistics": ["erp", "implementation", "bi"],
    "real estate": ["erp", "implementation", "support"],
    "hospitality": ["erp", "implementation", "ecommerce", "support"],
    "hotel": ["erp", "implementation", "support"],
    "restaurant": ["erp", "implementation", "support"],
}

# Default annual list prices (company currency) for auto-added Odoo products —
# editable on the product records afterwards.
LICENSE_PRICE = 1400.0   # per user / year
HOSTING_PRICE = 3600.0   # flat / year
LICENSE_NAME = "Odoo Enterprise User Licence (annual)"
HOSTING_NAME = "Odoo.sh Cloud Hosting (annual)"


def _strip_html(value):
    """Flatten an HTML field to plain text for the notes box."""
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


class C2pProposalWizard(models.TransientModel):
    _name = "c2p.proposal.wizard"
    _description = "C2P Proposal Maker"

    order_id = fields.Many2one(
        "sale.order", string="Existing Quotation",
        help="When launched from a quotation, its customer, lines and any saved "
             "proposal context are pulled in, and Generate updates that quotation.")
    lead_id = fields.Many2one(
        "crm.lead", string="Opportunity",
        help="When launched from a CRM opportunity, its customer and context "
             "are pulled in automatically.")
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True)
    proposal_title = fields.Char(
        string="Proposal Title",
        help="Leave blank to auto-title from the selected services.")
    industry = fields.Char(string="Client Industry")
    service_category_id = fields.Many2one(
        "product.category", string="Filter by category",
        help="Narrow the list below to one service category so it is easy to "
             "find and tick the relevant services. Leave empty to see all.")
    service_ids = fields.Many2many(
        "product.product", string="Services / Modules",
        domain=[("sale_ok", "=", True)],
        help="Tick every service or module this proposal should include.")
    template_id = fields.Many2one(
        "sale.order.template", string="Start from template",
        help="Optionally seed the proposal from a saved quotation template; "
             "ticked services are added on top.")
    validity_days = fields.Integer(string="Valid for (days)", default=30)
    timeline_weeks = fields.Integer(string="Indicative timeline (weeks)", default=12)
    # ── Intelligence ────────────────────────────────────────────────────────
    user_count = fields.Integer(
        string="Number of users", default=0,
        help="Odoo Enterprise licences and cloud hosting are auto-added for this "
             "many users so the proposal shows the full cost of ownership.")
    include_licenses = fields.Boolean(
        string="Add Odoo licences & hosting", default=True)
    package_tier = fields.Selection(
        [("starter", "Starter"), ("professional", "Professional"),
         ("enterprise", "Enterprise")],
        string="Suggested package", compute="_compute_intel")
    est_weeks = fields.Integer(string="Estimated timeline (weeks)", compute="_compute_intel")
    est_effort = fields.Char(string="Estimated effort", compute="_compute_intel")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company,
        help="The proposal is issued by this company; its base currency and "
             "pricelist drive the pricing (AED for C2P Consultants, PKR for "
             "Core 2 Plus / C2P Solutions).")
    pricelist_id = fields.Many2one(
        "product.pricelist", string="Pricelist",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Drives the proposal currency. Pick a multi-currency pricelist to "
             "quote the client in another currency.")
    amc_monthly = fields.Monetary(
        string="Monthly AMC", currency_field="currency_id",
        help="Optional post go-live maintenance, billed monthly. Shown as a "
             "separate AMC section on the proposal.")
    currency_id = fields.Many2one(
        "res.currency", string="Currency", compute="_compute_currency",
        store=True, readonly=True)
    exec_summary = fields.Text(string="Executive Summary (optional)")
    pain_points = fields.Text(
        string="Pain points (one per line)",
        help="Leave blank to use a sensible default set.")
    objectives = fields.Text(string="Objectives (one per line)")
    note = fields.Text(string="Notes / scope summary")
    open_pdf = fields.Boolean(
        string="Open proposal PDF immediately", default=True)

    # ── Company / pricelist / currency ──────────────────────────────────────
    @api.depends("pricelist_id", "company_id")
    def _compute_currency(self):
        for w in self:
            w.currency_id = (w.pricelist_id.currency_id
                             or w.company_id.currency_id
                             or self.env.company.currency_id)

    def _default_pricelist(self, company=None, partner=None):
        """The right sale pricelist for a company/partner (customer's own if it
        belongs to the company, else the company's first pricelist)."""
        company = company or self.company_id or self.env.company
        partner = partner or self.partner_id
        PL = self.env["product.pricelist"]
        if partner and partner.property_product_pricelist:
            pl = partner.property_product_pricelist
            if not pl.company_id or pl.company_id == company:
                return pl
        return PL.search(["|", ("company_id", "=", False),
                          ("company_id", "=", company.id)], limit=1)

    @api.onchange("company_id", "partner_id")
    def _onchange_company_partner(self):
        pl = self.pricelist_id
        if not pl or (pl.company_id and pl.company_id != self.company_id):
            self.pricelist_id = self._default_pricelist()

    @api.onchange("service_category_id")
    def _onchange_service_category(self):
        """Narrow the service checklist to the chosen category (ticked services
        in other categories stay selected)."""
        dom = [("sale_ok", "=", True)]
        if self.service_category_id:
            dom.append(("categ_id", "child_of", self.service_category_id.id))
        return {"domain": {"service_ids": dom}}

    # ── Auto-generated narrative content ────────────────────────────────────
    def _service_domains(self):
        names = [(p.name or "") + " " + (p.categ_id.name or "")
                 for p in self.service_ids]
        return classify_domains(names)

    def _gen_texts(self):
        """Generate exec summary, pain points and objectives from the selected
        services (+ client/industry) — deterministic, no API."""
        doms = self._service_domains()
        company = self.env.company.name
        partner = self.partner_id.name or "your organisation"
        scopes = [DOMAINS[d]["scope"] for d in doms]
        scope_txt = (scopes[0] if len(scopes) == 1
                     else ", ".join(scopes[:-1]) + " and " + scopes[-1])
        ind = (" in the %s sector" % self.industry) if self.industry else ""
        exec_summary = (
            "%s is pleased to present this proposal to %s%s for %s. Following our "
            "understanding of your requirements, this document sets out the proposed "
            "solution, our delivery approach, an indicative timeline and a transparent "
            "commercial proposal — delivered standard-first, phased and fully documented."
            % (company, partner, ind, scope_txt))
        pains, objs = [], []
        for d in doms:
            for p in DOMAIN_TEXT.get(d, {}).get("pains", []):
                if p not in pains:
                    pains.append(p)
            for o in DOMAIN_TEXT.get(d, {}).get("objectives", []):
                if o not in objs:
                    objs.append(o)
        return {"exec_summary": exec_summary,
                "pain_points": "\n".join(pains[:6]),
                "objectives": "\n".join(objs[:6])}

    @api.onchange("service_ids", "partner_id", "industry")
    def _onchange_generate_content(self):
        """Fill the narrative tabs from the selection (only where still empty, so
        manual edits survive). Use 'Regenerate content' to force a refresh."""
        if not self.service_ids:
            return
        gen = self._gen_texts()
        if not self.exec_summary:
            self.exec_summary = gen["exec_summary"]
        if not self.pain_points:
            self.pain_points = gen["pain_points"]
        if not self.objectives:
            self.objectives = gen["objectives"]

    def action_regenerate_content(self):
        """Force-regenerate the narrative tabs from the current selection."""
        self.ensure_one()
        self.update(self._gen_texts())
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new"}

    # ── Intelligence: estimation, recommendation, licences ──────────────────
    @api.depends("service_ids", "user_count")
    def _compute_intel(self):
        for w in self:
            n_mod = len(w.service_ids)
            users = w.user_count or 0
            weeks = min(40, 4 + int(round(1.6 * n_mod)) + (2 if users > 50 else 0))
            w.est_weeks = weeks
            lo = max(2, int(weeks * 0.7))
            w.est_effort = "%d-%d person-weeks" % (lo, int(weeks * 1.2))
            if users >= 50 or n_mod >= 6:
                w.package_tier = "enterprise"
            elif users >= 15 or n_mod >= 3:
                w.package_tier = "professional"
            else:
                w.package_tier = "starter"

    def action_recommend_services(self):
        """Tick the services typically recommended for the client's industry."""
        self.ensure_one()
        ind = (self.industry or "").lower()
        keys = []
        for k, v in INDUSTRY_RECO.items():
            if k in ind:
                keys = v
                break
        if not keys:
            keys = ["erp", "implementation", "support"]
        prods = self.env["product.product"].search([("sale_ok", "=", True)])
        picked = prods.filtered(
            lambda p: any(kw in (p.name or "").lower() for kw in keys))
        if picked:
            self.service_ids = [(4, p.id) for p in picked]
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new"}

    def _ensure_product(self, name, price):
        """Find or create a sellable service product (idempotent)."""
        Prod = self.env["product.product"]
        p = Prod.search([("name", "=", name)], limit=1)
        if not p:
            vals = {"name": name, "sale_ok": True, "purchase_ok": False,
                    "list_price": price}
            if "type" in Prod._fields:
                vals["type"] = "service"
            if "detailed_type" in Prod._fields:
                vals["detailed_type"] = "service"
            p = Prod.create(vals)
        return p

    def _license_lines(self):
        """Order-line commands for Odoo licences + hosting (per user)."""
        if not (self.include_licenses and self.user_count > 0):
            return []
        lic = self._ensure_product(LICENSE_NAME, LICENSE_PRICE)
        host = self._ensure_product(HOSTING_NAME, HOSTING_PRICE)
        return [(0, 0, {"product_id": lic.id, "product_uom_qty": self.user_count}),
                (0, 0, {"product_id": host.id, "product_uom_qty": 1})]

    # ── Pull context from a source record (order / opportunity) ─────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        order_id = ctx.get("default_order_id")
        lead_id = ctx.get("default_lead_id")
        if ctx.get("active_model") == "sale.order" and not order_id:
            order_id = ctx.get("active_id")
        if ctx.get("active_model") == "crm.lead" and not lead_id:
            lead_id = ctx.get("active_id")
        if order_id:
            order = self.env["sale.order"].browse(order_id)
            if order.exists():
                res.update(self._values_from_order(order))
        elif lead_id:
            lead = self.env["crm.lead"].browse(lead_id)
            if lead.exists():
                res.update(self._values_from_lead(lead))
        # Fill the company's default pricelist if nothing set one yet.
        if not res.get("pricelist_id"):
            company = (self.env["res.company"].browse(res["company_id"])
                       if res.get("company_id") else self.env.company)
            partner = (self.env["res.partner"].browse(res["partner_id"])
                       if res.get("partner_id") else None)
            pl = self._default_pricelist(company=company, partner=partner)
            if pl:
                res["pricelist_id"] = pl.id
                res.setdefault("company_id", company.id)
        return res

    def _values_from_order(self, order):
        """Pre-fill from an existing quotation."""
        vals = {
            "order_id": order.id,
            "partner_id": order.partner_id.id,
            "service_ids": [(6, 0, order.order_line.filtered(
                lambda l: not l.display_type and l.product_id).mapped("product_id").ids)],
        }
        if order.company_id:
            vals["company_id"] = order.company_id.id
        if "pricelist_id" in order._fields and order.pricelist_id:
            vals["pricelist_id"] = order.pricelist_id.id
        # Carry any previously saved proposal context.
        for src, dst in [("c2p_proposal_title", "proposal_title"),
                         ("c2p_industry", "industry"),
                         ("c2p_exec_summary", "exec_summary"),
                         ("c2p_pain_points", "pain_points"),
                         ("c2p_objectives", "objectives")]:
            if order._fields.get(src) and order[src]:
                vals[dst] = order[src]
        if "c2p_timeline_weeks" in order._fields and order.c2p_timeline_weeks:
            vals["timeline_weeks"] = order.c2p_timeline_weeks
        if "c2p_amc_monthly" in order._fields and order.c2p_amc_monthly:
            vals["amc_monthly"] = order.c2p_amc_monthly
        return vals

    def _values_from_lead(self, lead):
        """Map an opportunity's info onto the proposal fields."""
        vals = {"lead_id": lead.id}
        if lead.partner_id:
            vals["partner_id"] = lead.partner_id.id
        if lead.description:
            vals["note"] = _strip_html(lead.description)
        who = lead.partner_id.name or lead.partner_name or lead.contact_name or "the client"
        vals["exec_summary"] = (
            "%s is pleased to present this proposal to %s following our "
            "discussions around \"%s\". It sets out the proposed solution, "
            "delivery approach, timeline and commercials."
        ) % (self.env.company.name, who, lead.name or "your requirements")
        return vals

    @api.onchange("order_id")
    def _onchange_order_id(self):
        if self.order_id:
            for key, val in self._values_from_order(self.order_id).items():
                if key not in ("order_id", "service_ids"):
                    setattr(self, key, val)

    @api.onchange("lead_id")
    def _onchange_lead_id(self):
        if self.lead_id:
            for key, val in self._values_from_lead(self.lead_id).items():
                if key != "lead_id":
                    setattr(self, key, val)

    # ── Values ──────────────────────────────────────────────────────────────
    def _narrative_vals(self):
        vals = {
            "c2p_is_proposal": True,
            "c2p_proposal_title": self.proposal_title,
            "c2p_industry": self.industry,
            # Use the smart estimate unless the user set a non-default timeline.
            "c2p_timeline_weeks": (self.timeline_weeks
                                   if self.timeline_weeks and self.timeline_weeks != 12
                                   else (self.est_weeks or self.timeline_weeks)),
            "c2p_amc_monthly": self.amc_monthly,
            "c2p_exec_summary": self.exec_summary,
            "c2p_pain_points": self.pain_points,
            "c2p_objectives": self.objectives,
        }
        SO = self.env["sale.order"]
        if self.validity_days and "validity_date" in SO._fields:
            vals["validity_date"] = fields.Date.add(
                fields.Date.today(), days=self.validity_days)
        if self.note and "note" in SO._fields:
            vals["note"] = self.note
        return vals

    def _order_vals(self, order_lines):
        vals = dict(self._narrative_vals())
        vals["partner_id"] = self.partner_id.id
        vals["order_line"] = order_lines
        SO = self.env["sale.order"]
        if self.company_id:
            vals["company_id"] = self.company_id.id
        pricelist = self.pricelist_id or self._default_pricelist()
        if pricelist and "pricelist_id" in SO._fields:
            vals["pricelist_id"] = pricelist.id
        if self.template_id and "sale_order_template_id" in SO._fields:
            vals["sale_order_template_id"] = self.template_id.id
        if self.lead_id and "opportunity_id" in SO._fields:
            vals["opportunity_id"] = self.lead_id.id
        return vals

    def _print_or_open(self, order):
        if self.open_pdf:
            return self.env.ref(
                "c2p_proposal.action_report_c2p_proposal").report_action(order)
        return {
            "type": "ir.actions.act_window",
            "name": "Proposal",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_generate(self):
        """Update the source quotation (if any) or create one, then render the PDF."""
        self.ensure_one()
        if not self.service_ids and not self.template_id and not self.order_id:
            raise UserError(
                "Tick at least one service, or pick a template, to build the proposal.")

        if self.order_id:
            # Update the existing quotation in place: apply narrative context and
            # add any newly-ticked services + licences not already on the order.
            order = self.order_id
            order.write(self._narrative_vals())
            existing = order.order_line.mapped("product_id")
            for product in self.service_ids:
                if product not in existing:
                    self.env["sale.order.line"].create({
                        "order_id": order.id, "product_id": product.id,
                        "product_uom_qty": 1})
            for cmd in self._license_lines():
                vals = dict(cmd[2], order_id=order.id)
                if self.env["product.product"].browse(vals["product_id"]) not in existing:
                    self.env["sale.order.line"].create(vals)
            return self._print_or_open(order)

        order_lines = [(0, 0, {"product_id": p.id, "product_uom_qty": 1})
                       for p in self.service_ids]
        order_lines += self._license_lines()
        order = self.env["sale.order"].create(self._order_vals(order_lines))
        return self._print_or_open(order)
