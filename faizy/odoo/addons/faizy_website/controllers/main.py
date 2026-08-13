import logging
import re
from urllib.parse import quote

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# 00000-0000000-0
CNIC_RE = re.compile(r"^\d{5}-\d{7}-\d$")


def whatsapp_url(message):
    """A wa.me link for the company number, or None if there isn't one.

    `sudo()` because visitors are the public user, and reading res.company
    from that env comes back empty — which is what made the header's WhatsApp
    button dead-end to /contactus for everyone who pressed it.

    Module level rather than a method so the portal controller can reach it
    without importing a page controller; the number handling has to be the
    same everywhere or the links quietly disagree.
    """
    company = request.website.sudo().company_id or request.env.company.sudo()
    number = re.sub(r"^0+", "", re.sub(r"\D", "", company.phone or ""))
    if not 8 <= len(number) <= 15:
        _logger.warning(
            "Faizy: no usable company phone (%r), so the WhatsApp link was "
            "left off the page. Set it in Settings > Companies.",
            company.phone,
        )
        return None
    return f"https://wa.me/{number}?text={quote(message)}"


class FaizyWebsite(http.Controller):
    """Public pages: the pitch, the pricing, and the worker sign-up."""

    # Prefilled so the first message is already a sentence. Someone opening
    # WhatsApp to a blank compose box has to decide how to introduce
    # themselves, and a good share of them simply close it.
    WHATSAPP_OPENER = "Assalam o Alaikum! I'd like to know more about Faizy."
    WHATSAPP_SIGNUP_OPENER = "Assalam o Alaikum! I've just signed up for Faizy."

    def _whatsapp_url(self, message):
        return whatsapp_url(message)

    # ── Currency ─────────────────────────────────────────────────────────

    def _plan_currencies(self, plans):
        """Every currency we have actually published a price in, plus the
        company's own. Ordered by name so the switcher doesn't reshuffle
        between requests."""
        currencies = plans.mapped("price_ids.currency_id")
        currencies |= request.env.company.currency_id
        return currencies.sorted("name")

    def _display_currency(self, plans, requested=None):
        """Which currency to quote in.

        Customers are anywhere — the CRM has people in Dubai, Riyadh, London,
        Manchester and New York — so the price shown should be the one we
        published for that market. Preference order: what the visitor picked,
        then the currency of the country GeoIP puts them in, then PKR.

        PKR last rather than the company currency: the work is done in Pakistan
        and costed in rupees, and every other market price is a decision made
        on top of that one. A visitor we cannot place should see the rupee
        price, not whichever currency the company happens to report in.

        Only currencies with a published price are eligible. We never convert:
        a subscription price that moves with the exchange rate is not a price.
        """
        available = self._plan_currencies(plans)

        if requested:
            picked = available.filtered(
                lambda c: c.name == requested.strip().upper()
            )[:1]
            if picked:
                return picked

        # request.geoip is absent when no GeoIP database is installed, and its
        # country_code is None for unresolved addresses — both are normal.
        code = getattr(request, "geoip", None) and request.geoip.country_code
        if code:
            country = request.env["res.country"].sudo().search(
                [("code", "=", code)], limit=1
            )
            local = available.filtered(lambda c: c == country.currency_id)[:1]
            if local:
                return local

        return plans[:1].default_currency() if plans else request.env.company.currency_id

    def _pricing_values(self, currency=None):
        plans = (
            request.env["faizy.plan"]
            .sudo()
            .search([("active", "=", True)], order="sequence")
        )
        return {
            "plans": plans,
            "currencies": self._plan_currencies(plans),
            "display_currency": self._display_currency(plans, currency),
        }

    # ── Pages ────────────────────────────────────────────────────────────

    @http.route("/", type="http", auth="public", website=True, sitemap=True)
    def faizy_home(self, currency=None, **kw):
        values = self._pricing_values(currency)
        # Categories, not the 22 individual services. The home page answers
        # "can you help with my kind of problem"; the catalogue belongs where
        # somebody has already decided to buy.
        values["categories"] = (
            request.env["faizy.service.category"]
            .sudo()
            .search([], order="sequence")
        )
        # Real Faizies, photographed ones first — the section is a trust
        # signal, and a wall of initials is a weaker one than actual faces.
        # Sample records never reach the public site.
        values["workers"] = (
            request.env["faizy.worker"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("state", "=", "active"),
                    ("is_sample", "=", False),
                ],
                order="rating_avg desc, name",
                limit=8,
            )
            .sorted(lambda w: not w.image_128)
        )
        values["company"] = request.env.company
        return request.render("faizy_website.home", values)

    @http.route("/pricing", type="http", auth="public", website=True, sitemap=True)
    def faizy_pricing(self, currency=None, **kw):
        return request.render("faizy_website.pricing", self._pricing_values(currency))

    @http.route("/privacy", type="http", auth="public", website=True, sitemap=True)
    def faizy_privacy(self, **kw):
        """The privacy policy.

        Not optional paperwork for this product. We hold a family's home
        address, a mother's prescription and a worker's CNIC, and we send it
        all over WhatsApp — people are entitled to read what happens to that
        before they hand it over.
        """
        return request.render(
            "faizy_website.privacy",
            {
                "company": request.env.company,
                "whatsapp_number": request.env[
                    "faizy.whatsapp.message"
                ].sudo().contact_number(),
            },
        )

    @http.route("/whatsapp", type="http", auth="public", website=True, sitemap=False)
    def faizy_whatsapp(self, text=None, **kw):
        """Open a WhatsApp chat with us.

        A redirect rather than a wa.me link in the menu record, so the number
        has exactly one home — res.company.phone, the same field the FMB
        welcome message and the footer read. Change it in Settings and every
        surface follows.

        `sudo()` is load-bearing. Visitors are the public user, and reading
        res.company from that env comes back empty — so the number was blank,
        the guard below fired, and the button quietly landed on /contactus
        instead of opening WhatsApp. The footer never showed the symptom
        because QWeb reads `website.company_id`, which is already sudo'd.
        Nothing secret is exposed: this is the number printed in the footer.

        Falls back to the contact page rather than 404ing, but says so in the
        log — a header button that dead-ends because nobody filled in the
        company phone is worse than one that lands somewhere a human can still
        be reached, and a silent fallback is how this went unnoticed.
        """
        url = self._whatsapp_url(text or self.WHATSAPP_OPENER)
        if not url:
            # A header button that dead-ends because nobody filled in the
            # company phone is worse than one that lands somewhere a human can
            # still be reached. _whatsapp_url has already logged why.
            return request.redirect("/contactus")
        return request.redirect(url, local=False)

    @http.route(
        "/faizy/worker/<int:worker_id>/photo",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def faizy_worker_photo(self, worker_id, **kw):
        """Serve one active Faizy's photo, and nothing else about them.

        Not /web/image/faizy.worker/... — that route enforces the model ACL,
        and giving base.group_public read on faizy.worker to make it work would
        expose CNIC, phone number and pay rate to anyone who can reach a
        generic read route. The photo is the only field the public site needs,
        so this hands over exactly that.
        """
        worker = (
            request.env["faizy.worker"]
            .sudo()
            .search(
                [
                    ("id", "=", worker_id),
                    ("active", "=", True),
                    ("state", "=", "active"),
                    ("is_sample", "=", False),
                ],
                limit=1,
            )
        )
        if not worker or not worker.image_128:
            return request.not_found()
        return (
            request.env["ir.binary"]
            ._get_image_stream_from(worker, "image_128")
            .get_response()
        )

    # ── Customer sign-up ─────────────────────────────────────────────────
    #
    # One page, eight fields, no card. The three free activities are the
    # product's own answer to "why would I trust you" — asking for payment
    # details before we have done anything throws that away, and the payment
    # gateway is not chosen yet anyway. So signup creates the account and the
    # subscription stays in draft until somebody has actually been helped.

    def _signup_values(self, values=None, errors=None, plan_code=None):
        env = request.env
        plans = env["faizy.plan"].sudo().search(
            [("active", "=", True)], order="sequence"
        )
        return {
            "plans": plans,
            "countries": env["res.country"].sudo().search([], order="name"),
            "relationships": env["faizy.family.member"]
            ._fields["relationship"]
            .selection,
            "values": values or {},
            "errors": errors or {},
            "plan_code": plan_code or "standard",
        }

    @http.route("/start", type="http", auth="public", website=True, sitemap=True)
    def faizy_start(self, plan=None, **kw):
        return request.render(
            "faizy_website.signup", self._signup_values(values=kw, plan_code=plan)
        )

    @http.route(
        "/start/submit",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def faizy_start_submit(self, **post):
        """Create the customer, their first family member and a subscription.

        ⚠️ Anonymous POST. The honeypot stops naive bots and nothing more — the
        same CAPTCHA/rate-limit caveat as /join applies here, and more sharply,
        because this endpoint writes three records.
        """
        if post.get("website"):  # honeypot
            return request.redirect("/start/welcome")

        env = request.env
        errors = {}
        name = (post.get("name") or "").strip()
        phone = (post.get("phone") or "").strip()
        country_id = post.get("country_id")
        member_name = (post.get("member_name") or "").strip()
        member_city = (post.get("member_city") or "").strip()
        plan_code = post.get("plan") or "standard"

        # "This one is for me." Half the catalogue — passport, NADRA, FBR
        # filing, property visits — is the subscriber's own business waiting in
        # Pakistan, and the form used to insist on a family member, so there
        # was no way to buy the thing they came for.
        #
        # Resolved server-side rather than by hiding a field with script: a
        # checkbox that only changes the UI leaves the requirement in place,
        # and the person who has JS off gets an error they cannot clear.
        for_self = bool(post.get("for_self"))
        relationship = post.get("relationship") or "other"
        if for_self:
            relationship = "self"
            member_name = member_name or name

        if not name:
            errors["name"] = "Please tell us your name."
        if not phone:
            errors["phone"] = "We need your WhatsApp number — that is how we reach you."
        if not country_id:
            errors["country_id"] = "Where are you based?"
        # Only reachable when the box is unticked AND no name was typed —
        # ticking it borrows the subscriber's own name above.
        if not member_name:
            errors["member_name"] = (
                "Who are we caring for? Tick the box above if it is for you."
            )
        if not member_city:
            errors["member_city"] = "Which city in Pakistan is the help needed in?"

        plan = env["faizy.plan"].sudo().search([("code", "=", plan_code)], limit=1)
        if not plan:
            errors["plan"] = "Please choose a plan."

        if errors:
            return request.render(
                "faizy_website.signup",
                self._signup_values(values=post, errors=errors, plan_code=plan_code),
            )

        Partner = env["res.partner"].sudo()
        # Someone who signs up twice is a returning customer, not a duplicate.
        # Matching on phone keeps their FMB IDs and history attached.
        #
        # `phone` only: Odoo 19 removed res.partner.mobile — checked in
        # odoo/addons/base/models/res_partner.py, where 18.0 declares both and
        # 19.0 declares `phone = fields.Char()` alone. Searching or writing
        # `mobile` raises ValueError, which is what this route did on every
        # single signup until it was found.
        partner = Partner.search([("phone", "=", phone)], limit=1)
        if partner:
            partner.write({"is_faizy_customer": True, "name": partner.name or name})
        else:
            partner = Partner.create(
                {
                    "name": name,
                    "phone": phone,
                    "email": (post.get("email") or "").strip() or False,
                    "country_id": int(country_id),
                    "is_faizy_customer": True,
                }
            )

        member = env["faizy.family.member"].sudo().create(
            {
                "partner_id": partner.id,
                "name": member_name,
                "relationship": relationship,
                "city": member_city,
            }
        )

        # Draft, not active: nobody has been billed and nothing has been
        # delivered. Ops confirms once the first activity is arranged.
        subscription = env["faizy.subscription"].sudo().create(
            {"partner_id": partner.id, "plan_id": plan.id}
        )

        env["faizy.whatsapp.message"].sudo().queue_message(
            partner=partner,
            message_type="generic",
            body=env._(
                "Welcome to Faizy, %(name)s. %(member)s is registered as "
                "%(fmb)s. You have %(free)s free care activities — just reply "
                "here and tell us what they need.",
                name=partner.name,
                member=member.name,
                fmb=member.fmb_id,
                free=partner.faizy_free_activities,
            ),
        )
        subscription.message_post(
            body=env._("Signed up from the website on the %s plan.", plan.name)
        )
        return request.redirect(f"/start/welcome?fmb={member.fmb_id}")

    @http.route(
        "/start/welcome", type="http", auth="public", website=True, sitemap=False
    )
    def faizy_start_welcome(self, fmb=None, **kw):
        """The page after signing up.

        Carries a WhatsApp link with the member ID already written into it, so
        the first message ops receives identifies the customer instead of
        starting with "hi". Built here rather than in the template because the
        number needs the same sudo and the same digits-only normalisation as
        /whatsapp, and two places building the same URL is one place too many.
        """
        opener = self.WHATSAPP_SIGNUP_OPENER
        if fmb:
            opener = f"{opener} My family member ID is {fmb}."
        return request.render(
            "faizy_website.signup_welcome",
            {"fmb": fmb, "whatsapp_url": self._whatsapp_url(opener)},
        )

    # ── Worker sign-up ───────────────────────────────────────────────────

    @http.route("/join", type="http", auth="public", website=True, sitemap=True)
    def faizy_join(self, **kw):
        env = request.env
        return request.render(
            "faizy_website.join",
            {
                "services": env["faizy.service"].sudo().search([("active", "=", True)]),
                "areas": env["faizy.area"].sudo().search([("active", "=", True)]),
                "values": kw,
                "errors": {},
            },
        )

    @http.route(
        "/join/submit",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def faizy_join_submit(self, **post):
        """Accept an application from the public form.

        Validated server-side regardless of what the browser enforced — this
        endpoint is reachable directly.

        ⚠️ Anonymous POST needs abuse protection that application code cannot
        provide on its own. Put a CAPTCHA or per-IP rate limit in front of this
        before launch; the honeypot below stops naive bots and nothing more.
        """
        errors = {}

        # Honeypot: a real person never fills a hidden field.
        if post.get("website"):
            return request.redirect("/join/thanks?ref=")

        name = (post.get("name") or "").strip()
        phone = (post.get("phone") or "").strip()
        cnic = (post.get("cnic") or "").strip()
        city = (post.get("city") or "").strip()

        if not name:
            errors["name"] = "Please tell us your full name."
        if not phone:
            errors["phone"] = "We need a phone number to reach you on."
        if not CNIC_RE.match(cnic):
            errors["cnic"] = "CNIC should look like 00000-0000000-0."
        if not city:
            errors["city"] = "Which city do you work in?"
        if not post.get("code_of_conduct"):
            errors["code_of_conduct"] = "Please accept the code of conduct."
        if not post.get("rate_card"):
            errors["rate_card"] = "Please accept the rate card."

        if errors:
            env = request.env
            return request.render(
                "faizy_website.join",
                {
                    "services": env["faizy.service"].sudo().search([("active", "=", True)]),
                    "areas": env["faizy.area"].sudo().search([("active", "=", True)]),
                    "values": post,
                    "errors": errors,
                },
            )

        service_ids = [int(i) for i in request.httprequest.form.getlist("service_ids")]
        area_ids = [int(i) for i in request.httprequest.form.getlist("area_ids")]

        application = (
            request.env["faizy.application"]
            .sudo()
            .create(
                {
                    "name": name,
                    "phone": phone,
                    "cnic": cnic,
                    "email": (post.get("email") or "").strip() or False,
                    "city": city,
                    "service_ids": [(6, 0, service_ids)],
                    "area_ids": [(6, 0, area_ids)],
                    "availability": post.get("availability") or False,
                    "has_vehicle": bool(post.get("has_vehicle")),
                    "vehicle_type": post.get("vehicle_type") or False,
                    "experience_years": int(post.get("experience_years") or 0),
                    "experience_notes": post.get("experience_notes") or False,
                    "reference_contacts": post.get("reference_contacts") or False,
                    "code_of_conduct_accepted": True,
                    "rate_card_accepted": True,
                    "date_accepted": fields.Datetime.now(),
                }
            )
        )
        return request.redirect(f"/join/thanks?ref={application.reference}")

    @http.route("/join/thanks", type="http", auth="public", website=True, sitemap=False)
    def faizy_join_thanks(self, ref=None, **kw):
        return request.render("faizy_website.join_thanks", {"reference": ref})

    @http.route(
        "/join/status", type="http", auth="public", website=True, sitemap=False
    )
    def faizy_join_status(self, reference=None, phone=None, **kw):
        """Let an applicant check progress with their reference plus phone.

        Both are required together — a reference number alone would let anyone
        enumerate applications, which hold CNICs and selfies.
        """
        application = None
        searched = bool(reference and phone)
        if searched:
            application = (
                request.env["faizy.application"]
                .sudo()
                .search(
                    [
                        ("reference", "=", reference.strip().upper()),
                        ("phone", "=", phone.strip()),
                    ],
                    limit=1,
                )
            )
        return request.render(
            "faizy_website.join_status",
            {
                "application": application,
                "searched": searched,
                "reference": reference,
                "phone": phone,
            },
        )
