from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    marketplace_alt_count = fields.Integer(
        compute="_compute_marketplace_alt_count",
        string="Marketplace Vendors",
    )

    def _compute_marketplace_alt_count(self):
        Listing = self.env["mumtaz.marketplace.listing"].sudo()
        for order in self:
            order.marketplace_alt_count = Listing.search_count(
                order._marketplace_alternatives_domain()
            )

    def _marketplace_alternatives_domain(self):
        product_ids = self.order_line.mapped("product_id.product_tmpl_id").ids
        categ_ids = self.order_line.mapped("product_id.categ_id").ids

        base = [
            ("state", "=", "published"),
            ("company_id", "!=", self.env.company.id),
            ("listing_type", "=", "product"),
        ]

        if product_ids:
            return base + [
                "|",
                ("product_tmpl_id", "in", product_ids),
                ("category_id.name", "in", self._po_category_keywords(categ_ids)),
            ]
        return base

    def _po_category_keywords(self, categ_ids):
        categs = self.env["product.category"].browse(categ_ids)
        return [c.name.split("/")[-1].strip() for c in categs] or ["General"]

    def action_view_marketplace_alternatives(self):
        self.ensure_one()
        domain = self._marketplace_alternatives_domain()
        return {
            "type": "ir.actions.act_window",
            "name": "Marketplace Vendor Alternatives",
            "res_model": "mumtaz.marketplace.listing",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"po_id": self.id},
        }

    def action_marketplace_send_rfq(self):
        self.ensure_one()
        lines_summary = "\n".join(
            f"- {l.product_id.display_name}: {l.product_qty} {l.product_uom.name}"
            for l in self.order_line
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Send RFQ to Marketplace",
            "res_model": "mumtaz.marketplace.po.rfq.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_order_id": self.id,
                "default_message": (
                    f"RFQ from {self.env.company.name}:\n\n{lines_summary}\n\n"
                    f"Delivery required by: {self.date_order.strftime('%Y-%m-%d') if self.date_order else 'ASAP'}"
                ),
                "default_inquirer_name": self.env.user.name,
                "default_inquirer_email": self.env.user.email or self.env.company.email or "",
                "default_inquirer_company": self.env.company.name,
            },
        }


class MarketplacePORFQWizard(models.TransientModel):
    _name = "mumtaz.marketplace.po.rfq.wizard"
    _description = "Send RFQ to Marketplace from Purchase Order"

    purchase_order_id = fields.Many2one("purchase.order", readonly=True)
    listing_id = fields.Many2one(
        "mumtaz.marketplace.listing",
        string="Target Supplier Listing",
        domain=[("state", "=", "published")],
        required=True,
    )
    inquirer_name = fields.Char("Your Name", required=True)
    inquirer_email = fields.Char("Your Email", required=True)
    inquirer_company = fields.Char("Your Company")
    inquirer_phone = fields.Char("Phone")
    message = fields.Text("Requirements", required=True)

    def action_send(self):
        self.ensure_one()
        self.env["mumtaz.marketplace.inquiry"].create({
            "listing_id": self.listing_id.id,
            "company_id": self.env.company.id,
            "inquirer_name": self.inquirer_name,
            "inquirer_email": self.inquirer_email,
            "inquirer_company": self.inquirer_company or self.env.company.name,
            "inquirer_phone": self.inquirer_phone or "",
            "message": self.message,
        })
        if self.purchase_order_id:
            self.purchase_order_id.message_post(
                body=(
                    f"<b>Marketplace RFQ sent</b> to <i>{self.listing_id.name}</i> "
                    f"({self.listing_id.company_id.name}) via Mumtaz Marketplace."
                )
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "RFQ Sent",
                "message": f"Your RFQ has been sent to {self.listing_id.company_id.name}.",
                "type": "success",
                "sticky": False,
            },
        }
