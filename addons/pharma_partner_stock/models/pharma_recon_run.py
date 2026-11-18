from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError


def _whole(qty, label):
    """The roll-forward counts whole units. A fractional quantity is refused, not rounded away."""
    whole = round(qty)
    if abs(qty - whole) > 1e-6:
        raise UserError("Fractional quantity %s for %s: the roll-forward counts whole units. "
                        "Correct the stock move first." % (qty, label))
    return int(whole)


class PharmaReconRun(models.Model):
    _inherit = "pharma.recon.run"

    partner_location_id = fields.Many2one(
        "stock.location", string="Partner Location", domain="[('usage', 'in', ('internal', 'transit'))]",
        help="The partner's stock location. Moves between this location and its sub-locations are ignored; "
             "only moves that cross its boundary count.")
    date_from = fields.Date(string="Period From")
    date_to = fields.Date(string="Period To")

    # ------------------------------------------------------------------ derivation
    def action_compute_stock_from_moves(self):
        if not self.env.user.has_group("pharma_core.group_pharma_finance"):
            raise UserError("Only a Finance Controller can compute the stock roll-forward.")
        for run in self:
            if run.run_type != "partner_stock":
                raise UserError("Only a Distribution Partner stock run can be computed from stock moves.")
            if not (run.partner_location_id and run.date_from and run.date_to):
                raise UserError("Choose the partner location and the period first.")
            if run.date_to < run.date_from:
                raise UserError("Period To cannot be before Period From.")
            run._derive_stock_lines()
        return True

    def _derive_stock_lines(self):
        self.ensure_one()
        loc = self.partner_location_id
        inside = self.env["stock.location"].sudo().search([("id", "child_of", loc.id)]).ids
        ML = self.env["stock.move.line"].sudo()
        start = fields.Datetime.to_datetime(self.date_from)
        end = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        done = [("state", "=", "done")]
        crossing_in = [("location_dest_id", "in", inside), ("location_id", "not in", inside)]
        crossing_out = [("location_id", "in", inside), ("location_dest_id", "not in", inside)]
        in_period = [("date", ">=", start), ("date", "<", end)]

        def total(domain):
            rows = ML._read_group(done + domain, ["product_id", "lot_id"], ["quantity_product_uom:sum"])
            return {(p, l): q for p, l, q in rows}

        opening_in = total(crossing_in + [("date", "<", start)])
        opening_out = total(crossing_out + [("date", "<", start)])
        # Inventory adjustments (source usage 'inventory') join the opening position, because the goods are
        # physically there, but are never added to a period column: the difference shows as variance.
        inward = total(crossing_in + in_period + [("location_id.usage", "!=", "inventory")])
        sold = total(crossing_out + in_period + [("location_dest_id.usage", "=", "customer")])
        returned = total(crossing_out + in_period + [("location_dest_id.usage", "in", ("internal", "transit"))])
        scrapped = total(crossing_out + in_period + [("move_id.scrap_id", "!=", False)])

        keys = set()
        for d in (opening_in, opening_out, inward, sold, returned, scrapped):
            keys |= set(d)
        existing = {(l.sku, l.lot): l for l in self.stock_line_ids if l.location == loc.complete_name}
        touched = set()
        created = updated = 0
        for product, lot in sorted(keys, key=lambda k: (k[0].default_code or k[0].display_name, k[1].name or "")):
            sku = product.default_code or product.display_name
            lot_name = lot.name or "(no lot)"
            label = "%s / %s" % (sku, lot_name)
            vals = {
                "opening": _whole(opening_in.get((product, lot), 0.0) - opening_out.get((product, lot), 0.0), label),
                "inward_accepted": _whole(inward.get((product, lot), 0.0), label),
                "sold_or_issued": _whole(sold.get((product, lot), 0.0), label),
                "returned_to_pharma": _whole(returned.get((product, lot), 0.0), label),
                "expired_damaged_documented": _whole(scrapped.get((product, lot), 0.0), label),
                "from_stock_moves": True,
            }
            line = existing.get((sku, lot_name))
            if line:
                line.write(vals)
                updated += 1
            else:
                self.env["pharma.partner.stock.line"].create(dict(
                    vals, run_id=self.id, sku=sku, lot=lot_name, location=loc.complete_name, is_demo=self.is_demo))
                created += 1
            touched.add((sku, lot_name))
        zeroed = 0
        for key, line in existing.items():
            if key not in touched and line.from_stock_moves:
                line.write({"opening": 0, "inward_accepted": 0, "sold_or_issued": 0,
                            "returned_to_pharma": 0, "expired_damaged_documented": 0})
                zeroed += 1
        self.message_post(body="Stock roll-forward computed from stock moves for %s, %s to %s: %d lines created, "
                               "%d updated, %d zeroed. Approved adjustments and the partner's reported counts were not touched."
                               % (loc.complete_name, self.date_from, self.date_to, created, updated, zeroed))
