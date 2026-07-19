from markupsafe import Markup

from odoo import fields, models


def _win(title, body):
    """Wrap SVG body in a consistent charcoal 'application window' frame.

    ``title``/``body`` are hardcoded, module-internal SVG constants (never user
    input), so wrapping them in Markup is safe. nosec silences bandit B704.
    """
    return Markup(  # nosec B704
        '<svg viewBox="0 0 340 150" width="100%%" height="150" '
        'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" '
        'style="display:block;background:#fff;border:1px solid #e2e6ea;border-radius:6px;">'
        '<rect x="0" y="0" width="340" height="24" fill="#1e2a33"/>'
        '<circle cx="14" cy="12" r="3" fill="#e0575b"/>'
        '<circle cx="25" cy="12" r="3" fill="#e6b34d"/>'
        '<circle cx="36" cy="12" r="3" fill="#14b3a8"/>'
        '<text x="170" y="16" fill="#c3cad6" font-family="Segoe UI,Arial" '
        'font-size="9" text-anchor="middle">%s</text>%s</svg>' % (title, body))


# On-brand "system preview" illustrations per service domain (inline SVG, no
# external assets — print-safe). Swap the body of any entry for a real product
# screenshot later without touching the report.
def _kpi(x, val, lbl):
    return ('<rect x="%d" y="34" width="98" height="34" rx="4" fill="#f4f7f8" stroke="#e8ecef"/>'
            '<text x="%d" y="51" fill="#1e2a33" font-family="Segoe UI,Arial" font-size="12" '
            'font-weight="bold">%s</text><text x="%d" y="62" fill="#9aa1ac" '
            'font-family="Segoe UI,Arial" font-size="7">%s</text>' % (x, x + 8, val, x + 8, lbl))


def _bars(x0, y0, heights, col="#14b3a8"):
    out = ""
    for i, h in enumerate(heights):
        out += '<rect x="%d" y="%d" width="12" height="%d" rx="1" fill="%s"/>' % (
            x0 + i * 18, y0 - h, h, col)
    return out


_ERP = _kpi(12, "1.2M", "Revenue") + _kpi(121, "3 d", "Close") + _kpi(230, "98%", "On-time") \
    + _bars(20, 138, [18, 30, 24, 40, 34, 46], "#14b3a8") \
    + '<circle cx="270" cy="112" r="24" fill="none" stroke="#e8ecef" stroke-width="8"/>' \
      '<path d="M270 88 A24 24 0 0 1 291 124" fill="none" stroke="#14b3a8" stroke-width="8"/>' \
    + '<text x="150" y="90" fill="#9aa1ac" font-family="Segoe UI,Arial" font-size="8">Sales &#183; Stock &#183; Finance</text>'

_DEV = '<rect x="12" y="34" width="150" height="104" rx="4" fill="#1e2a33"/>' \
    + "".join('<rect x="24" y="%d" width="%d" height="5" rx="2" fill="%s"/>' % (
        46 + i * 14, w, c) for i, (w, c) in enumerate(
        [(70, "#14b3a8"), (110, "#5b6b78"), (90, "#5b6b78"), (120, "#14b3a8"),
         (80, "#5b6b78"), (100, "#5b6b78")])) \
    + '<rect x="188" y="34" width="70" height="104" rx="8" fill="#f4f7f8" stroke="#cfd6db"/>' \
      '<rect x="196" y="44" width="54" height="7" rx="3" fill="#1e2a33"/>' \
      '<rect x="196" y="58" width="54" height="20" rx="3" fill="#bfe6e2"/>' \
      '<rect x="196" y="84" width="54" height="7" rx="3" fill="#cfd6db"/>' \
      '<rect x="196" y="96" width="54" height="7" rx="3" fill="#cfd6db"/>' \
      '<circle cx="223" cy="126" r="9" fill="#14b3a8"/>' \
    + '<text x="300" y="90" fill="#9aa1ac" font-family="Segoe UI,Arial" font-size="8" text-anchor="middle">App</text>'

_BI = '<polyline points="14,120 60,96 106,104 152,72 198,84 244,50 300,40" fill="none" ' \
      'stroke="#14b3a8" stroke-width="3"/>' \
    + "".join('<circle cx="%d" cy="%d" r="3" fill="#1e2a33"/>' % p for p in
              [(60, 96), (152, 72), (244, 50), (300, 40)]) \
    + _bars(20, 138, [10, 16, 12, 20, 15, 22, 18], "#bfe6e2") \
    + '<circle cx="290" cy="112" r="22" fill="none" stroke="#e8ecef" stroke-width="7"/>' \
      '<path d="M290 90 A22 22 0 1 1 271 123" fill="none" stroke="#14b3a8" stroke-width="7"/>' \
    + '<text x="20" y="46" fill="#9aa1ac" font-family="Segoe UI,Arial" font-size="8">KPI Dashboard</text>'

_FIN = '<rect x="60" y="34" width="220" height="104" rx="4" fill="#fff" stroke="#e8ecef"/>' \
      '<rect x="60" y="34" width="220" height="18" fill="#f4f7f8"/>' \
      '<text x="70" y="46" fill="#1e2a33" font-family="Segoe UI,Arial" font-size="8" font-weight="bold">TAX INVOICE</text>' \
    + "".join('<rect x="70" y="%d" width="130" height="5" rx="2" fill="#dfe4e8"/>'
              '<rect x="230" y="%d" width="40" height="5" rx="2" fill="#cfd6db"/>' % (y, y)
              for y in [64, 78, 92]) \
    + '<line x1="70" y1="108" x2="270" y2="108" stroke="#e8ecef"/>' \
      '<rect x="170" y="116" width="100" height="16" rx="3" fill="#1e2a33"/>' \
      '<text x="220" y="127" fill="#fff" font-family="Segoe UI,Arial" font-size="8" text-anchor="middle">Total  VAT 5%</text>'

_CON = "".join(
    '<rect x="%d" y="60" width="60" height="30" rx="4" fill="#f4f7f8" stroke="#cfd6db"/>' % x
    for x in [16, 96, 176, 256]) \
    + "".join('<line x1="%d" y1="75" x2="%d" y2="75" stroke="#14b3a8" stroke-width="2"/>'
              '<polygon points="%d,71 %d,75 %d,79" fill="#14b3a8"/>' % (x + 60, x + 96, x + 92, x + 96, x + 92)
              for x in [16, 96, 176]) \
    + "".join('<text x="%d" y="78" fill="#6b7280" font-family="Segoe UI,Arial" font-size="7" '
              'text-anchor="middle">%s</text>' % (x + 30, t)
              for x, t in [(16, "As-Is"), (96, "Gap"), (176, "To-Be"), (256, "SOP")]) \
    + "".join('<rect x="16" y="%d" width="10" height="10" rx="2" fill="#14b3a8"/>'
              '<rect x="32" y="%d" width="%d" height="4" rx="2" fill="#dfe4e8"/>' % (y, y + 3, w)
              for y, w in [(104, 150), (120, 120)])

_TRN = '<rect x="12" y="34" width="150" height="90" rx="4" fill="#1e2a33"/>' \
      '<polygon points="78,68 78,90 98,79" fill="#14b3a8"/>' \
      '<rect x="24" y="104" width="126" height="5" rx="2" fill="#5b6b78"/>' \
      '<rect x="24" y="104" width="80" height="5" rx="2" fill="#14b3a8"/>' \
    + "".join('<circle cx="188" cy="%d" r="6" fill="none" stroke="#14b3a8" stroke-width="2"/>'
              '<path d="M185 %d l2 2 4 -4" stroke="#14b3a8" stroke-width="2" fill="none"/>'
              '<rect x="202" y="%d" width="%d" height="5" rx="2" fill="#dfe4e8"/>' % (y, y, y - 3, w)
              for y, w in [(46, 120), (66, 100), (86, 130), (106, 90)])

_SUP = "".join(
    '<rect x="14" y="%d" width="312" height="22" rx="4" fill="#f4f7f8" stroke="#e8ecef"/>'
    '<circle cx="28" cy="%d" r="4" fill="%s"/>'
    '<rect x="42" y="%d" width="150" height="5" rx="2" fill="#cfd6db"/>'
    '<rect x="250" y="%d" width="62" height="12" rx="6" fill="%s"/>'
    '<text x="281" y="%d" fill="#fff" font-family="Segoe UI,Arial" font-size="7" text-anchor="middle">%s</text>'
    % (y, y + 11, col, y + 9, y + 5, pill, y + 14, lbl)
    for y, col, pill, lbl in [
        (34, "#e0575b", "#14b3a8", "Resolved"), (60, "#e6b34d", "#e6b34d", "In SLA"),
        (86, "#14b3a8", "#14b3a8", "Resolved"), (112, "#e6b34d", "#6b7280", "Open")])

VISUALS = {
    "erp": ("Unified ERP Dashboard", _win("Dashboard", _ERP)),
    "development": ("Custom Application", _win("Application", _DEV)),
    "analytics": ("Live BI Dashboard", _win("Analytics", _BI)),
    "finance": ("Compliant Invoicing", _win("Accounting", _FIN)),
    "consulting": ("Process & SOPs", _win("Process Design", _CON)),
    "training": ("Training & Enablement", _win("Learning", _TRN)),
    "support": ("Support & SLA Desk", _win("Helpdesk", _SUP)),
}

# ── Service domains ─────────────────────────────────────────────────────────
# Each order line's product is classified into one or more domains by keyword
# (product name + category). The proposal's methodology, deliverables, benefits,
# solution intro and title are then composed from the domains actually selected —
# so the document reads correctly for ERP, development, analytics, consulting,
# finance, training or support engagements (or any mix), not just Odoo ERP.
_DOMAIN_ORDER = ["erp", "development", "consulting", "analytics",
                 "finance", "training", "support"]

DOMAINS = {
    "erp": {
        "keywords": ["erp", "implementation", "brd", "professional package",
                     "starter package", "customization", "customisation",
                     "odoo consulting", "go-live", "migration"],
        "scope": "a fully integrated Odoo ERP configured standard-first",
        "title": "Odoo ERP Implementation Proposal",
        "phases": [
            ("Discovery & Requirement Analysis",
             "Structured workshops to document current processes, pains, data "
             "sources and success criteria; sign-off on a Business Requirements "
             "Document (BRD)."),
            ("Solution Design & Gap-Fit",
             "Map requirements to standard Odoo, identify configuration vs. "
             "customisation, and agree the target process design (FRS)."),
            ("Configuration & Base Setup",
             "Company, chart of accounts, taxes, users, security and the in-scope "
             "apps configured on a dedicated environment."),
            ("Customisation & Development",
             "Any approved custom modules, reports and integrations built on top "
             "of standard Odoo - inherited, never forked."),
            ("Data Migration",
             "Clean, map and load master and opening data (customers, vendors, "
             "products, balances) with validation and reconciliation."),
            ("Training & UAT",
             "Role-based user training and a formal User Acceptance Testing cycle "
             "against the agreed test scripts."),
            ("Go-Live & Cutover",
             "Final data load, go/no-go checklist, production cutover and "
             "hyper-care support in the first weeks of operation."),
            ("Post Go-Live Support & AMC",
             "Ongoing support, issue resolution, enhancements and periodic health "
             "checks under the Annual Maintenance Contract."),
        ],
        "deliverables": [
            "Business Requirements Document (BRD) and Functional Requirements Spec (FRS).",
            "Configured Odoo environment for every in-scope application.",
            "Migrated and reconciled master and opening data.",
            "UAT sign-off, go-live cutover and hyper-care support.",
        ],
        "benefits": [
            {"title": "One unified platform",
             "desc": "Every department on a single source of truth."},
            {"title": "Automation",
             "desc": "Manual, repetitive work eliminated across processes."},
        ],
        "erp": True,
    },
    "development": {
        "keywords": ["development", "web", "mobile", "ecommerce", "e-commerce",
                     "apex", "integration", "api", " ai", "agent", "automation",
                     "application", "software", "portal"],
        "scope": "custom software built to your requirements",
        "title": "Software Development Proposal",
        "phases": [
            ("Discovery & Requirements",
             "Workshops to capture requirements, users and success criteria; a "
             "signed-off scope."),
            ("Solution & UX Design",
             "Architecture, data model and UX / wireframes agreed before build."),
            ("Development",
             "Built in iterative sprints with regular demos and feedback."),
            ("QA & Testing",
             "Functional, integration and performance testing against acceptance "
             "criteria."),
            ("UAT & Acceptance",
             "Client testing against agreed scripts and formal sign-off."),
            ("Deployment & Handover",
             "Production release, documentation and knowledge transfer."),
            ("Support & Enhancements",
             "Warranty support and a managed backlog for future enhancements."),
        ],
        "deliverables": [
            "Signed-off requirements and UX / wireframes.",
            "The built and tested application or integration.",
            "Test reports and UAT sign-off.",
            "Deployment, source handover and documentation.",
        ],
        "benefits": [
            {"title": "Purpose-built",
             "desc": "Fits your exact workflow, not a generic template."},
            {"title": "Automation that scales",
             "desc": "Manual steps replaced with reliable, repeatable software."},
        ],
    },
    "consulting": {
        "keywords": ["process", "sop", "reengineering", "re-engineering", "bpr",
                     "change management", "gap analysis", "business process", "audit"],
        "scope": "process re-engineering with documented SOPs",
        "title": "Business Process Consulting Proposal",
        "phases": [
            ("Discovery & As-Is Mapping",
             "Map current processes with owners, inputs, outputs and pain points."),
            ("Gap Analysis",
             "Compare as-is against best practice and the target operating model."),
            ("To-Be Design",
             "Design improved processes with quantified benefits."),
            ("SOPs & Change Plan",
             "Author standard operating procedures and an adoption / change plan."),
            ("Handover & Enablement",
             "Train process owners and hand over the documented processes."),
        ],
        "deliverables": [
            "As-is process maps with owners and pain points.",
            "Gap analysis against best practice.",
            "To-be process design with quantified improvements.",
            "Standard Operating Procedures (SOPs) and a change plan.",
        ],
        "benefits": [
            {"title": "Leaner processes",
             "desc": "Waste and manual effort removed from day-to-day operations."},
            {"title": "Change that sticks",
             "desc": "Documented SOPs and enablement drive real adoption."},
        ],
    },
    "analytics": {
        "keywords": ["dashboard", "analytics", "reporting", "business intelligence",
                     "power bi", "insight"],
        "scope": "KPI dashboards and BI on your live data",
        "title": "Analytics & BI Proposal",
        "phases": [
            ("Discovery & KPI Definition",
             "Agree the questions, KPIs and metrics that matter."),
            ("Data Modelling",
             "Connect and model the source data into a reliable dataset."),
            ("Dashboard Build",
             "Build interactive dashboards and reports on the model."),
            ("Validation & UAT",
             "Validate numbers against source and get user sign-off."),
            ("Rollout & Training",
             "Publish, secure and train users on the dashboards."),
        ],
        "deliverables": [
            "Agreed KPI and metric framework.",
            "Connected and modelled dataset.",
            "Interactive dashboards and reports.",
            "User training and access setup.",
        ],
        "benefits": [
            {"title": "Real-time insight",
             "desc": "Decisions on current data, not last month's guess."},
            {"title": "One version of the truth",
             "desc": "Everyone works from the same trusted numbers."},
        ],
    },
    "finance": {
        "keywords": ["vat", "zatca", "tax", "finance", "advisory", "cfo", "ifrs",
                     "bookkeeping", "compliance", "fta"],
        "scope": "GCC tax, VAT and IFRS advisory",
        "title": "Finance & Compliance Advisory Proposal",
        "phases": [
            ("Discovery & Scoping",
             "Understand the entity, records, regime and obligations."),
            ("Records & Data Review",
             "Review books, transactions and supporting documents for the period."),
            ("Analysis & Computation",
             "Compute tax / VAT positions and analyse against the regime."),
            ("Report & Recommendations",
             "Document findings, exposures and recommended actions."),
            ("Filing & Sign-off Support",
             "Prepare returns / working papers and support submission (client-approved)."),
        ],
        "deliverables": [
            "Compliance and exposure assessment.",
            "Computations and working papers.",
            "Advisory report with recommendations.",
            "Return preparation and filing support.",
        ],
        "benefits": [
            {"title": "Compliant & audit-ready",
             "desc": "Positions assessed against FTA / ZATCA and IFRS."},
            {"title": "Accurate, on-time",
             "desc": "Returns and reports prepared right, on schedule."},
        ],
    },
    "training": {
        "keywords": ["training", "enablement", "workshop", "adoption"],
        "scope": "role-based training and enablement",
        "title": "Training & Enablement Proposal",
        "phases": [
            ("Training Needs Analysis",
             "Identify roles, skill gaps and learning objectives."),
            ("Material Preparation",
             "Prepare role-based curricula, guides and exercises."),
            ("Delivery",
             "Run instructor-led sessions, on-site or remote."),
            ("Assessment & Handover",
             "Assess competency and hand over materials for reuse."),
        ],
        "deliverables": [
            "Training plan and curriculum.",
            "Role-based materials and user manuals.",
            "Delivered training sessions.",
            "Competency assessment and handover.",
        ],
        "benefits": [
            {"title": "Confident users",
             "desc": "Teams that actually use the system well."},
            {"title": "Faster adoption",
             "desc": "Less post go-live friction and support load."},
        ],
    },
    "support": {
        "keywords": ["support", "amc", "maintenance", "hypercare", "sla"],
        "scope": "ongoing SLA-backed support and maintenance",
        "title": "Support & AMC Proposal",
        "phases": [
            ("Onboarding & Baseline",
             "Document the environment, access and support scope."),
            ("Issue Triage & Resolution",
             "Log, prioritise and resolve issues within SLA."),
            ("Enhancements",
             "Deliver small changes and improvements from a managed backlog."),
            ("Health Checks & Reporting",
             "Periodic system health checks and a support report."),
        ],
        "deliverables": [
            "SLA-backed support desk.",
            "Resolved issues and change log.",
            "Periodic health checks.",
            "Support and usage reporting.",
        ],
        "benefits": [
            {"title": "System kept healthy",
             "desc": "Proactive checks catch issues before they bite."},
            {"title": "Predictable cost",
             "desc": "A fixed monthly envelope for peace of mind."},
        ],
    },
}

_BASE_BENEFITS = [
    {"title": "GCC-native",
     "desc": "AED / PKR, IFRS, 5% VAT and ZATCA-aware from day one."},
    {"title": "One accountable partner",
     "desc": "Business and technical expertise under one roof."},
    {"title": "Documented & governed",
     "desc": "Clear scope, sign-off gates and knowledge transfer."},
]

# Per-domain pain points and objectives used to auto-generate proposal content.
DOMAIN_TEXT = {
    "erp": {
        "pains": ["Disconnected spreadsheets and apps with no single source of truth.",
                  "Manual, error-prone data entry duplicated across departments.",
                  "Limited real-time visibility into operations and finance."],
        "objectives": ["Unify core operations on a single integrated platform.",
                       "Automate cross-department workflows and reporting.",
                       "Give management real-time dashboards and control."]},
    "development": {
        "pains": ["Off-the-shelf tools don't fit the way you actually work.",
                  "Manual, repetitive tasks that should be automated.",
                  "Systems that don't talk to each other."],
        "objectives": ["Deliver software built precisely to your process.",
                       "Automate the manual, repetitive work.",
                       "Integrate your systems into one reliable flow."]},
    "consulting": {
        "pains": ["Processes undocumented and inconsistent between people.",
                  "Bottlenecks and rework nobody has quantified.",
                  "Change initiatives that don't stick."],
        "objectives": ["Map and streamline the priority processes.",
                       "Remove bottlenecks with quantified improvements.",
                       "Embed change with SOPs and enablement."]},
    "analytics": {
        "pains": ["Reporting is manual, slow and inconsistent.",
                  "No single, trusted version of the numbers.",
                  "Decisions made on stale data."],
        "objectives": ["Build trusted, real-time dashboards.",
                       "Consolidate data into one reliable model.",
                       "Enable faster, evidence-based decisions."]},
    "finance": {
        "pains": ["Tax/VAT and statutory work assembled late and by hand.",
                  "Uncertainty over compliance and exposure.",
                  "Management accounts that are never quite current."],
        "objectives": ["Ensure accurate, on-time tax and statutory compliance.",
                       "Assess and close exposure against the regime.",
                       "Produce reliable, timely management reporting."]},
    "training": {
        "pains": ["Users under-trained, so the system is under-used.",
                  "Knowledge concentrated in a few people.",
                  "Slow, painful adoption after go-live."],
        "objectives": ["Build confident, capable users across roles.",
                       "Document and spread knowledge.",
                       "Accelerate adoption and reduce support load."]},
    "support": {
        "pains": ["Issues linger without a clear owner or SLA.",
                  "No proactive maintenance or health checks.",
                  "Unpredictable, reactive support costs."],
        "objectives": ["Resolve issues quickly under a clear SLA.",
                       "Keep the platform healthy with proactive checks.",
                       "Make support cost predictable."]},
}


def classify_domains(texts):
    """Domain keys present in a list of free-text strings (product/category
    names). Shared by the sale.order report and the Proposal Maker wizard."""
    low = [(t or "").lower() for t in texts]
    found = [k for k in _DOMAIN_ORDER
             if any(any(kw in t for kw in DOMAINS[k]["keywords"]) for t in low)]
    return found or ["erp"]


class SaleOrder(models.Model):
    """Proposal-specific narrative fields layered on top of a quotation.

    The Proposal Maker wizard creates a normal ``sale.order`` (so pricing,
    taxes, templates and the CRM pipeline all keep working) and stores the
    narrative context here. The branded ``c2p_proposal`` QWeb report then
    renders a full document whose sections adapt to the services selected.
    """

    _inherit = "sale.order"

    c2p_is_proposal = fields.Boolean(
        string="Is C2P Proposal", default=False, copy=False,
        help="Marks orders created through the Proposal Maker so the branded "
             "proposal report is offered.")
    c2p_proposal_title = fields.Char(
        string="Proposal Title",
        help="Leave blank to auto-title from the selected services.")
    c2p_exec_summary = fields.Text(string="Executive Summary")
    c2p_pain_points = fields.Text(
        string="Pain Points / Requirements",
        help="One challenge per line — rendered as a bullet list on the proposal.")
    c2p_objectives = fields.Text(
        string="Objectives", help="One objective per line.")
    c2p_industry = fields.Char(string="Client Industry")
    c2p_timeline_weeks = fields.Integer(string="Indicative Timeline (weeks)", default=12)
    c2p_amc_monthly = fields.Monetary(
        string="Monthly AMC", currency_field="currency_id",
        help="Optional post go-live annual maintenance contract, billed monthly.")
    c2p_hosting_note = fields.Text(
        string="Licensing & Hosting Note",
        help="Leave blank to auto-add the Odoo licence note when an ERP is in scope.")

    # ── Service-domain classification ───────────────────────────────────────
    def _c2p_domain_keys(self):
        """Ordered list of service domains present in the order lines."""
        self.ensure_one()
        texts = []
        for line in self.order_line:
            if line.display_type or not line.product_id:
                continue
            cat = line.product_id.categ_id.name if line.product_id.categ_id else ""
            texts.append((line.product_id.name or "") + " " + (cat or ""))
        return classify_domains(texts)

    def _c2p_anchor(self):
        return self._c2p_domain_keys()[0]

    def _c2p_has_erp(self):
        return "erp" in self._c2p_domain_keys()

    # ── Composed narrative (adapts to the selected services) ────────────────
    def _c2p_lines_to_bullets(self, text):
        return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

    def _c2p_pain_list(self):
        self.ensure_one()
        pains = self._c2p_lines_to_bullets(self.c2p_pain_points)
        if pains:
            return pains
        return [
            "Disconnected spreadsheets and standalone apps with no single source of truth.",
            "Manual, error-prone data entry duplicated across departments.",
            "Limited real-time visibility into operations and finance.",
            "Compliance and reporting handled outside the system, late and by hand.",
            "No scalable platform to support growth into new markets or entities.",
        ]

    def _c2p_objective_list(self):
        self.ensure_one()
        objs = self._c2p_lines_to_bullets(self.c2p_objectives)
        if objs:
            return objs
        return [
            "Unify and streamline core operations.",
            "Automate cross-department workflows to cut manual effort and errors.",
            "Give management real-time dashboards and reliable reporting.",
            "Ensure statutory and tax compliance is handled reliably.",
            "Build a scalable foundation that grows with the business.",
        ]

    @staticmethod
    def _c2p_pairs(items):
        return [items[i:i + 2] for i in range(0, len(items), 2)]

    def _c2p_benefit_rows(self):
        return self._c2p_pairs(self._c2p_benefits())

    def _c2p_why_rows(self):
        return self._c2p_pairs(self._c2p_why_choose())

    def _c2p_benefits(self):
        """Benefits composed from the selected domains, padded with base ones."""
        out = []
        for dom in self._c2p_domain_keys():
            for b in DOMAINS[dom]["benefits"]:
                if b not in out:
                    out.append(b)
        for b in _BASE_BENEFITS:
            if len(out) >= 6:
                break
            if b not in out:
                out.append(b)
        return out[:6]

    def _c2p_methodology(self):
        """Delivery methodology of the anchor (primary) domain."""
        phases = DOMAINS[self._c2p_anchor()]["phases"]
        return [{"n": i + 1, "name": name, "desc": desc}
                for i, (name, desc) in enumerate(phases)]

    def _c2p_deliverables(self):
        out = []
        for dom in self._c2p_domain_keys():
            for d in DOMAINS[dom]["deliverables"]:
                if d not in out:
                    out.append(d)
        return out[:8]

    def _c2p_visuals(self):
        """On-brand system-preview panels for the selected service domains."""
        out = []
        for d in self._c2p_domain_keys():
            if d in VISUALS:
                out.append({"title": VISUALS[d][0], "svg": VISUALS[d][1]})
        return out[:4]

    def _c2p_visual_rows(self):
        return self._c2p_pairs(self._c2p_visuals())

    def _c2p_kpis(self):
        """The four cover/summary KPIs (navy band): timeline, modules, users, fee."""
        lines = self.order_line.filtered(lambda l: not l.display_type and l.product_id)
        modules = len(lines) - len(lines.filtered(lambda l: self._c2p_is_license_line(l)))
        users = 0
        for l in lines:
            n = (l.product_id.name or "").lower()
            if "licence" in n or "license" in n:
                users = int(l.product_uom_qty)
        weeks = self.c2p_timeline_weeks or 12
        tl = "%d Weeks" % weeks if weeks < 9 else "%d Months" % max(1, round(weeks / 4.0))
        return {
            "timeline": tl,
            "modules": "%d Module%s" % (modules, "" if modules == 1 else "s"),
            "users": ("%d Users" % users) if users else "As required",
            "investment": self._c2p_cost_split()["implementation"],
        }

    def _c2p_expertise(self):
        return [
            "Odoo Enterprise Certified Partner",
            "End-to-end ERP: sales, stock, finance, manufacturing, HR",
            "Standard-first configuration, custom only where it adds value",
            "GCC & Pakistan: AED/PKR, IFRS, VAT/ZATCA, multi-company",
            "Data migration, training and gated go-live",
            "Post go-live support & AMC",
        ]

    def _c2p_is_license_line(self, line):
        n = (line.product_id.name or "").lower()
        return any(k in n for k in ("licence", "license", "hosting",
                                    "subscription", "odoo.sh"))

    def _c2p_cost_split(self):
        """Split the order into implementation vs licences/hosting for a TCO view."""
        impl = lic = 0.0
        for line in self.order_line.filtered(lambda l: not l.display_type):
            if self._c2p_is_license_line(line):
                lic += line.price_subtotal
            else:
                impl += line.price_subtotal
        return {"implementation": impl, "licences": lic,
                "tax": self.amount_tax, "total": self.amount_total}

    def _c2p_line_scope(self, line):
        """Scope text for a line without repeating the product name."""
        name = (line.product_id.name or "").strip()
        txt = (line.name or "").strip()
        if name and txt.startswith(name):
            txt = txt[len(name):].strip(" -\n\t")
        return txt or "Configured and delivered as part of this engagement."

    def _c2p_timeline(self):
        """Phased delivery timeline (week ranges) sized to the indicative weeks."""
        w = max(self.c2p_timeline_weeks or 12, 5)
        stages = [("Discovery & Design", 0.20, "BRD & FRS signed off"),
                  ("Configuration & Build", 0.35, "System configured & customised"),
                  ("Data Migration", 0.15, "Data loaded & reconciled"),
                  ("Training & UAT", 0.20, "UAT sign-off"),
                  ("Go-Live & Hypercare", 0.10, "Production go-live")]
        out, start = [], 1
        for i, (name, frac, ms) in enumerate(stages):
            dur = max(1, round(w * frac)) if i < len(stages) - 1 else max(1, w - start + 1)
            end = start + dur - 1
            span = "Week %d" % start if dur == 1 else "Weeks %d-%d" % (start, end)
            out.append({"stage": name, "weeks": span, "milestone": ms})
            start = end + 1
        return out

    def _c2p_scope_in(self):
        items = [self._c2p_line_scope(l) if False else (l.product_id.name or "")
                 for l in self.order_line.filtered(lambda x: not x.display_type and x.product_id)]
        items += ["Configuration, testing and go-live of the above.",
                  "Documentation (BRD/FRS), training and hypercare support."]
        # de-dup while preserving order
        seen, out = set(), []
        for i in items:
            if i and i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def _c2p_scope_out(self):
        return [
            "Third-party software licences (billed directly by the vendor).",
            "Hardware, servers, network and infrastructure procurement.",
            "Data cleansing beyond the agreed migration template.",
            "Processes, modules or integrations not listed in this proposal.",
            "Support beyond the hypercare window (covered under a separate AMC).",
        ]

    def _c2p_payment_schedule(self):
        total = self.amount_total or 0.0
        rows = [("On engagement / mobilisation", 0.40),
                ("On UAT sign-off", 0.40),
                ("On production go-live", 0.20)]
        return [{"milestone": m, "pct": int(round(f * 100)), "amount": total * f}
                for m, f in rows]

    def _c2p_solution_intro(self):
        scopes = [DOMAINS[d]["scope"] for d in self._c2p_domain_keys()]
        if len(scopes) == 1:
            body = scopes[0]
        else:
            body = ", ".join(scopes[:-1]) + " and " + scopes[-1]
        return "This engagement delivers %s." % body

    def _c2p_default_title(self):
        doms = self._c2p_domain_keys()
        if len(doms) >= 3:
            return "Digital Transformation Proposal"
        return DOMAINS[self._c2p_anchor()]["title"]

    def _c2p_title(self):
        return self.c2p_proposal_title or self._c2p_default_title()

    def _c2p_exec_default(self):
        company = self.company_id.name or "We"
        partner = self.partner_id.name or "your organisation"
        return ("%s is pleased to present this proposal to %s. It sets out our "
                "understanding of your requirements, the proposed solution, our "
                "delivery approach, indicative timeline and a transparent "
                "commercial proposal." % (company, partner))

    def _c2p_hosting_note(self):
        if self.c2p_hosting_note:
            return self.c2p_hosting_note
        if self._c2p_has_erp():
            return ("Odoo Enterprise licences and Odoo.sh / cloud hosting are "
                    "billed separately by Odoo S.A. at published rates and are "
                    "not included in the fees above.")
        return ""

    def _c2p_roles(self):
        roles = [
            {"party": self.company_id.name or "C2P Consultants", "resp":
                "Project management, solution design, delivery, testing, training "
                "and go-live / handover."},
            {"party": "Client", "resp":
                "Nominate a sponsor and key users, provide timely access to data "
                "and SMEs, validate designs and complete UAT sign-off."},
        ]
        if self._c2p_has_erp():
            roles.append({"party": "Odoo S.A.", "resp":
                "Enterprise licensing, the Odoo.sh / cloud hosting platform and "
                "underlying product maintenance."})
        return roles

    def _c2p_assumptions(self):
        return [
            "Pricing is based on the scope and services listed in this proposal; "
            "material changes will be handled through a change request.",
            "The client provides timely inputs, data and feedback at each "
            "sign-off gate.",
            "Environments and access required for delivery are made available.",
            "Third-party licences and hosting are contracted separately unless stated.",
            "Work is delivered remotely with on-site visits as mutually agreed.",
        ]

    def _c2p_why_choose(self):
        return [
            {"title": "Business + technical depth",
             "desc": "Finance, tax and process consultants working alongside "
                     "developers, not just coders."},
            {"title": "Standard-first discipline",
             "desc": "We use proven best practice first and build custom only "
                     "where it adds real value - lower cost, easier upgrades."},
            {"title": "GCC & Pakistan expertise",
             "desc": "AED / PKR, IFRS, VAT / ZATCA and multi-company handled "
                     "natively."},
            {"title": "Method, not heroics",
             "desc": "Documented scope, sign-off gates and knowledge transfer on "
                     "every engagement."},
            {"title": "Long-term partnership",
             "desc": "Support, AMC and advisory retainers keep things healthy "
                     "after go-live."},
        ]

    def _c2p_next_steps(self):
        return [
            "Confirm acceptance of this proposal and commercial terms.",
            "Sign the engagement and raise the mobilisation invoice.",
            "Schedule the kick-off and discovery.",
        ]
