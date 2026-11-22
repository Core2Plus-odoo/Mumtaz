import logging

_logger = logging.getLogger(__name__)

# The live structure as inspected on 2026-10-05. Ids are a hint, not a
# contract: every entry is re-matched by name and partner, and a mismatch is
# logged rather than raised, so installing on a copy or a re-seeded database
# cannot fail here.
PAIRS = [
    # (portfolio id, delivery id, client name fragment)
    (14, 17, "TUV Austria"),
    (15, 21, "Medics"),
    (16, 19, "Aaban"),
    (18, 20, "Ghandhara"),
]
TEMPLATE_IDS = [2, 3, 4, 5, 6, 7, 8, 13]
# Known commercials; the rest are left at zero and flagged by
# commercials_missing, which drives an amber rule rather than a silent gap.
COMMERCIALS = {
    14: {"contract_value": 15000.0, "amount_received": 3000.0},
    16: {"contract_value": 10000.0, "amount_received": 6000.0},
}
GROUP_ASSIGNMENTS = [
    ("group_c2p_portfolio_manager", ["muhammad.umer@core2plus.com"]),
    ("group_c2p_delivery_lead", ["shafat.ali@core2plus.com"]),
    ("group_c2p_delivery_member", [
        "zeeshan.iqbal@core2plus.com", "fahad.siddiqui@core2plus.com",
        "talha.rauf@core2plus.com", "nida.aslam@core2plus.com",
        "hassan.javed@core2plus.com", "kamran.mest@core2plus.com",
        "sulaiman.mest@core2plus.com", "usman.mest@core2plus.com",
    ]),
]


def _resolve_project(env, project_id, client_fragment, expect_company_kind):
    """Find a project by id, falling back to client name and company.

    Ids drift between databases, so the fallback is the point: it is what makes
    this hook safe to run on a duplicate.
    """
    project = env["project.project"].browse(project_id).exists()
    if project and client_fragment.lower() in (project.name or "").lower():
        return project

    domain = [("name", "ilike", client_fragment)]
    if expect_company_kind == "portfolio":
        domain.append(("name", "ilike", "milestone"))
    else:
        domain.append(("name", "ilike", "delivery"))
    found = env["project.project"].search(domain, limit=1)
    if found:
        _logger.info(
            "c2p_project_tracker: project id %s did not match %r; matched %s "
            "by name instead", project_id, client_fragment, found.id)
        return found
    _logger.warning(
        "c2p_project_tracker: no project found for id %s / %r — skipped",
        project_id, client_fragment)
    return env["project.project"].browse()


def post_init_hook(env):
    """Adopt the existing structure without changing any of it destructively."""
    Project = env["project.project"]

    # 1. Classify. Archived projects are left alone: project 9 is a superseded
    # TUV project and must not appear in any dashboard.
    templates = Project.browse(TEMPLATE_IDS).exists()
    if templates:
        templates.write({"c2p_layer": "template"})
    internal = Project.search([("name", "=", "Internal")])
    if internal:
        internal.write({"c2p_layer": "internal"})

    matched = 0
    for portfolio_id, delivery_id, fragment in PAIRS:
        portfolio = _resolve_project(env, portfolio_id, fragment, "portfolio")
        delivery = _resolve_project(env, delivery_id, fragment, "delivery")
        if not portfolio or not delivery:
            continue
        portfolio.write({"c2p_layer": "portfolio"})
        delivery.write({"c2p_layer": "delivery"})
        # write() mirrors the link onto the counterpart.
        portfolio.write({"c2p_counterpart_id": delivery.id})
        matched += 1

        # 2. Match milestones by M-code.
        _match_milestones(env, portfolio, delivery)

        # 3. Seed commercials by the project's resolved id.
        values = COMMERCIALS.get(portfolio.id) or COMMERCIALS.get(portfolio_id)
        if values:
            portfolio.write(dict(values, subcontract_pct=60.0))

    _logger.info("c2p_project_tracker: paired %s of %s engagements",
                 matched, len(PAIRS))

    # 4. First sync and health pass.
    portfolios = Project.search([("c2p_layer", "=", "portfolio")])
    if portfolios:
        changed = portfolios._c2p_sync_portfolio_milestones()
        portfolios._compute_health()
        _logger.info("c2p_project_tracker: first sync changed %s milestones",
                     changed)

    # 5. Groups.
    _assign_groups(env)


def _match_milestones(env, portfolio, delivery):
    """Link each portfolio milestone task to the delivery milestone sharing its
    M-code. Unmatched codes are logged, not raised."""
    delivery_by_code = {}
    for milestone in env["project.milestone"].search(
            [("project_id", "=", delivery.id)]):
        code = (milestone.name or "").split()[0].upper() if milestone.name else ""
        if code.startswith("M"):
            delivery_by_code[code] = milestone

    linked = unmatched = 0
    for task in portfolio._c2p_milestones():
        target = delivery_by_code.get((task.c2p_code or "").upper())
        if target:
            task.write({"delivery_milestone_id": target.id})
            linked += 1
        else:
            unmatched += 1
            _logger.info(
                "c2p_project_tracker: %s has no delivery milestone %r in %s",
                task.name, task.c2p_code, delivery.name)
    _logger.info("c2p_project_tracker: %s linked %s milestones (%s unmatched)",
                 portfolio.name, linked, unmatched)


def _assign_groups(env):
    """Put the known users in their groups, by login rather than by id.

    Logins are stable where ids are not, and a login that does not exist is
    logged and skipped — the brief names a Portfolio Manager ("Abid Imtiaz")
    who has no user account on this database.
    """
    for group_name, logins in GROUP_ASSIGNMENTS:
        group = env.ref(f"c2p_project_tracker.{group_name}", raise_if_not_found=False)
        if not group:
            _logger.warning("c2p_project_tracker: group %s missing", group_name)
            continue
        users = env["res.users"].search([("login", "in", logins)])
        found = set(users.mapped("login"))
        for login in logins:
            if login not in found:
                _logger.warning(
                    "c2p_project_tracker: no user %r — not added to %s",
                    login, group_name)
        if users:
            group.write({"user_ids": [(4, user.id) for user in users]})
            _logger.info("c2p_project_tracker: %s → %s users",
                         group_name, len(users))
