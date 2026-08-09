from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class FaizySampleData(models.TransientModel):
    """Loads a realistic slice of the business so a fresh instance can be judged.

    Not Odoo demo data: that only loads at install, and the production database
    was created without it. This is an explicit action ops runs from the menu,
    which also means it can be run on a staging copy without touching how the
    real database was built.

    Everything it creates is tagged `sample=True` so it can all be removed again
    in one go. It refuses to run if real orders already exist, because the point
    is to fill an empty instance, not to salt a live one with fiction.
    """

    _name = "faizy.sample.data"
    _description = "Faizy Sample Data Loader"

    @api.model
    def _guard(self):
        if not self.env.user.has_group("faizy_core.group_faizy_manager"):
            raise UserError(self.env._("Only a Faizy Manager can load sample data."))
        real = self.env["faizy.order"].search_count([("is_sample", "=", False)])
        if real:
            raise UserError(
                self.env._(
                    "This database already has %(n)s real order(s). Sample data is "
                    "for empty instances — remove it first if you meant to reset.",
                    n=real,
                )
            )

    def action_load(self):
        self._guard()
        env = self.env
        today = fields.Date.context_today(self)

        service = {
            code: env.ref(f"faizy_core.service_{code}", raise_if_not_found=False)
            for code in ("groceries", "medicine", "doctor_visit", "documents",
                         "companionship", "emergency")
        }
        plan = {
            code: env.ref(f"faizy_core.plan_{code}", raise_if_not_found=False)
            for code in ("lite", "standard", "family_pro")
        }

        # ── The ground network ───────────────────────────────────────────
        workers = env["faizy.worker"].create([
            {"name": "Ahmed Raza", "phone": "+923001234567", "cnic": "42101-1234567-1",
             "city": "Karachi", "state": "active", "is_available": True,
             "base_rate": 1500, "is_sample": True},
            {"name": "Fatima Bibi", "phone": "+923011234568", "cnic": "35202-2345678-2",
             "city": "Lahore", "state": "active", "is_available": True,
             "base_rate": 1500, "is_sample": True},
            {"name": "Usman Khalid", "phone": "+923211234569", "cnic": "61101-3456789-3",
             "city": "Islamabad", "state": "active", "is_available": True,
             "base_rate": 1800, "is_sample": True},
        ])

        # ── The vendors we buy through ───────────────────────────────────
        # The supply side of an order. Without at least one, the commission
        # figures on the dashboard are all zero and the revenue model looks
        # like it does not work.
        vendors = env["res.partner"].create([
            {"name": "Al-Shifa Pharmacy", "is_company": True,
             "phone": "+924235559001", "city": "Lahore",
             "country_id": env.ref("base.pk").id,
             "is_faizy_vendor": True, "faizy_vendor_type": "pharmacy",
             "faizy_vendor_state": "active", "faizy_vendor_onboarded": today,
             "faizy_vendor_note": "Delivers Model Town before noon. Ask for Adnan.",
             "is_sample": True},
            {"name": "Green Valley Kiryana", "is_company": True,
             "phone": "+922134559002", "city": "Karachi",
             "country_id": env.ref("base.pk").id,
             "is_faizy_vendor": True, "faizy_vendor_type": "grocery",
             "faizy_vendor_state": "active", "faizy_vendor_onboarded": today,
             "is_sample": True},
            # A negotiated rate, so the override path is visible on a real
            # record rather than only in the field's help text.
            {"name": "Islamabad Diagnostics", "is_company": True,
             "phone": "+925135559003", "city": "Islamabad",
             "country_id": env.ref("base.pk").id,
             "is_faizy_vendor": True, "faizy_vendor_type": "lab",
             "faizy_vendor_state": "active", "faizy_vendor_onboarded": today,
             "faizy_vendor_custom_commission": True,
             "faizy_vendor_commission_rate": 0.15,
             "is_sample": True},
            {"name": "Rahat Medical Store", "is_company": True,
             "phone": "+924235559004", "city": "Lahore",
             "country_id": env.ref("base.pk").id,
             "is_faizy_vendor": True, "faizy_vendor_type": "pharmacy",
             "faizy_vendor_state": "prospect", "is_sample": True},
        ])
        shifa, kiryana, diagnostics, _prospect = vendors

        # ── Customers, wherever they are ─────────────────────────────────
        # Two in the Gulf and one in the UK, because that is the shape of the
        # real book — anyone demoing on sample data should see a non-AED
        # subscriber straight away rather than assume the Gulf is all of it.
        customers = env["res.partner"].create([
            {"name": "Bilal Rehman", "phone": "+971501234567", "email": "bilal@example.ae",
             "city": "Dubai", "country_id": env.ref("base.ae").id,
             "is_faizy_customer": True, "is_sample": True},
            {"name": "Ayesha Khan", "phone": "+966551234567", "email": "ayesha@example.sa",
             "city": "Riyadh", "country_id": env.ref("base.sa").id,
             "is_faizy_customer": True, "is_sample": True},
            {"name": "Hamza Siddiqui", "phone": "+447700900123", "email": "hamza@example.co.uk",
             "city": "London", "country_id": env.ref("base.uk").id,
             "is_faizy_customer": True, "is_sample": True},
        ])
        bilal, ayesha, hamza = customers

        # ── The families back home ───────────────────────────────────────
        members = env["faizy.family.member"].create([
            {"partner_id": bilal.id, "name": "Nasreen Rehman", "relationship": "mother",
             "city": "Lahore", "area": "Model Town", "phone": "+924235551234",
             "medical_notes": "Hypertension. Amlodipine 5mg daily. Check BP monthly.",
             "is_sample": True},
            {"partner_id": bilal.id, "name": "Imran Rehman", "relationship": "father",
             "city": "Lahore", "area": "Model Town", "is_sample": True},
            {"partner_id": ayesha.id, "name": "Zubaida Khan", "relationship": "mother",
             "city": "Karachi", "area": "Gulshan-e-Iqbal", "phone": "+922134551234",
             "medical_notes": "Diabetic. Metformin twice daily. Needs help at appointments.",
             "is_sample": True},
            {"partner_id": hamza.id, "name": "Abdul Siddiqui", "relationship": "father",
             "city": "Islamabad", "area": "F-10", "is_sample": True},
            {"partner_id": hamza.id, "name": "Sana Siddiqui", "relationship": "sibling",
             "city": "Islamabad", "area": "F-10", "is_sample": True},
        ])
        nasreen, imran, zubaida, abdul, sana = members

        # ── Subscriptions ────────────────────────────────────────────────
        subs = env["faizy.subscription"].create([
            {"partner_id": bilal.id, "plan_id": plan["standard"].id, "state": "active",
             "activities_included": plan["standard"].activities_included,
             "activities_used": 6, "is_sample": True},
            {"partner_id": ayesha.id, "plan_id": plan["family_pro"].id, "state": "active",
             "activities_included": plan["family_pro"].activities_included,
             "activities_used": 12, "is_sample": True},
        ])
        # Hamza stays on the free grant, so the paywall path is visible too.

        # ── Orders across every stage of the board ───────────────────────
        def order(customer, member, svc, title, state, days_ago, purchase=0.0,
                  fee=0.0, worker=None, rating=None, vendor=None):
            vals = {
                "partner_id": customer.id,
                "family_member_id": member.id if member else False,
                "service_id": service[svc].id,
                "title": title,
                "city": member.city if member else customer.city,
                "purchase_value": purchase,
                "service_fee": fee,
                "worker_id": worker.id if worker else False,
                # This parameter existed and was never written, so every sample
                # order had zero commission — the one number that proves the
                # revenue model was the one the sample data could not show.
                "vendor_id": vendor.id if vendor else False,
                "is_sample": True,
            }
            rec = env["faizy.order"].create(vals)
            when = fields.Datetime.now() - relativedelta(days=days_ago)
            if state in ("assigned", "in_progress", "completed"):
                rec.write({"state": state, "date_assigned": when})
            if state in ("in_progress", "completed"):
                rec.write({"date_started": when})
            if state == "completed":
                rec.write({"date_completed": when, "rating": rating,
                           "completion_note": "Delivered and confirmed with the family."})
            if state == "cancelled":
                rec.write({"state": "cancelled",
                           "cancellation_reason": "Family rescheduled."})
            return rec

        order(bilal, nasreen, "medicine", "Monthly BP medication", "completed", 3,
              84.0, 15.0, workers[1], "5", vendor=shifa)
        order(bilal, nasreen, "groceries", "Weekly groceries", "completed", 10,
              210.0, 20.0, workers[1], "4", vendor=kiryana)
        order(bilal, imran, "documents", "NADRA card renewal", "in_progress", 1,
              0.0, 45.0, workers[1])
        order(ayesha, zubaida, "doctor_visit", "Diabetes clinic — accompany", "completed", 5,
              0.0, 60.0, workers[0], "5")
        order(ayesha, zubaida, "medicine", "Metformin refill", "assigned", 0,
              66.0, 15.0, workers[0], vendor=shifa)
        order(ayesha, zubaida, "companionship", "Afternoon visit", "pending", 0)
        order(hamza, abdul, "groceries", "Eid grocery run", "completed", 20,
              340.0, 25.0, workers[2], "4", vendor=kiryana)
        # The 15% vendor, so a negotiated rate shows a different figure.
        order(hamza, abdul, "doctor_visit", "Blood panel at the lab", "completed", 14,
              120.0, 20.0, workers[2], "5", vendor=diagnostics)
        order(hamza, sana, "documents", "University transcript collection", "pending", 0)
        order(hamza, abdul, "emergency", "Welfare check after storm", "cancelled", 7)

        # A recurring template, so the pattern is visible on the board.
        env["faizy.order"].create({
            "partner_id": bilal.id,
            "family_member_id": nasreen.id,
            "service_id": service["groceries"].id,
            "title": "Weekly groceries (recurring)",
            "city": nasreen.city,
            "service_fee": 20.0,
            "is_recurring": True,
            "recurrence_type": "weekly",
            "recurrence_interval": 1,
            "recurrence_next_date": today + relativedelta(days=3),
            "is_sample": True,
        })

        # ── Documents on file ────────────────────────────────────────────
        env["faizy.document"].create([
            {"partner_id": bilal.id, "family_member_id": nasreen.id,
             "name": "Nasreen — CNIC", "doc_type": "cnic",
             "expiry_date": today + relativedelta(months=14), "is_sample": True},
            {"partner_id": bilal.id, "family_member_id": imran.id,
             "name": "Imran — Passport", "doc_type": "passport",
             "expiry_date": today + relativedelta(days=45), "is_sample": True},
            {"partner_id": ayesha.id, "family_member_id": zubaida.id,
             "name": "Zubaida — Diabetes care plan", "doc_type": "medical",
             "is_sample": True},
        ])

        # ── A worker application waiting in the pipeline ─────────────────
        env["faizy.application"].create({
            "name": "Kashif Mehmood", "phone": "+923331234570",
            "cnic": "42201-9876543-5", "city": "Karachi",
            "experience_years": 3,
            "experience_notes": "Three years with a pharmacy delivery service.",
            "reference_contacts": "Dr Salman, employer, +922134559999",
            "code_of_conduct_accepted": True, "rate_card_accepted": True,
            "is_sample": True,
        })

        env["faizy.bridge.request"].create({
            "partner_id": ayesha.id, "family_member_id": zubaida.id,
            "subject": "Speak to the consultant about the new dosage",
            "counterparty_name": "Dr Ali, Aga Khan",
            "details": "Wants to hear the plan directly before the next refill.",
            "is_sample": True,
        })

        env["faizy.product.request"].create({
            "partner_id": hamza.id, "family_member_id": abdul.id,
            "product_name": "Blood pressure monitor (Omron)",
            "description": "Upper-arm cuff, digital display.",
            "quantity": 1, "max_budget": 180.0, "is_sample": True,
        })

        subs.flush_recordset()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Sample data loaded"),
                "message": self.env._(
                    "3 customers, 5 family members, 3 Faizies, 4 vendors and "
                    "11 orders. Remove it any time from Configuration."
                ),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_remove(self):
        """Delete everything the loader created. Real records are untouched."""
        self._guard_manager()
        for model in ("faizy.document", "faizy.product.request", "faizy.bridge.request",
                      "faizy.order", "faizy.subscription", "faizy.application",
                      "faizy.family.member", "faizy.worker"):
            self.env[model].search([("is_sample", "=", True)]).unlink()
        self.env["res.partner"].search([("is_sample", "=", True)]).unlink()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Sample data removed"),
                "message": self.env._("Only real records remain."),
                "type": "success",
                "sticky": False,
            },
        }

    def _guard_manager(self):
        if not self.env.user.has_group("faizy_core.group_faizy_manager"):
            raise UserError(self.env._("Only a Faizy Manager can change sample data."))
