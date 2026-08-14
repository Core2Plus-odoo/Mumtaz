"""Give the company its free-activity grant, and the customers who never got it.

`res.company.faizy_free_activity_grant` carries `default=3`. An Odoo field
default applies when a *record* is created, not when a *column* is added — and
the Faizy company row predates faizy_core's install, so the column arrived on
it as 0. Every partner created since inherited that 0 through
`res.partner.faizy_free_activities`, whose own default reads the company grant.

The effect on the live database: /start promises "Three free activities. No
card needed", every customer signed up with none, and the first thing any of
them would have met is the paywall. It went unseen because the number is only
surfaced on a page nobody had opened as a customer until tonight.

Two steps, both conservative:

  * The company grant, only where it is 0 or NULL. A deliberate 0 is
    indistinguishable from the bug — but a deliberate 0 alongside a website
    advertising three is not a state anyone chose.
  * Customers sitting at 0 who have never consumed an activity. Someone who
    spent their three legitimately also reads 0, so the activity log is what
    separates them: no rows at all means the grant never arrived. Anyone who
    has spent even one is left alone.

`res.partner.company_id` is null for ordinary contacts, so the partner step
cannot join through it. It uses the single operating company instead, and
declines to guess when there is more than one — the same stance
apply_company_profile takes.
"""

import logging

_logger = logging.getLogger(__name__)

DEFAULT_GRANT = 3


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE res_company
           SET faizy_free_activity_grant = %s
         WHERE faizy_free_activity_grant IS NULL
            OR faizy_free_activity_grant = 0
        """,
        (DEFAULT_GRANT,),
    )
    if cr.rowcount:
        _logger.warning(
            "faizy_core: %s company/companies had no free-activity grant and "
            "were set to %s. Every customer created before this signed up with "
            "zero free activities.",
            cr.rowcount,
            DEFAULT_GRANT,
        )

    cr.execute("SELECT id, faizy_free_activity_grant FROM res_company")
    companies = cr.fetchall()
    if len(companies) != 1:
        _logger.info(
            "faizy_core: %s companies present, leaving customer balances alone",
            len(companies),
        )
        return

    grant = companies[0][1] or DEFAULT_GRANT
    cr.execute(
        """
        UPDATE res_partner p
           SET faizy_free_activities = %s
         WHERE p.is_faizy_customer IS TRUE
           AND COALESCE(p.faizy_free_activities, 0) = 0
           AND NOT EXISTS (
                 SELECT 1 FROM faizy_activity_log l WHERE l.partner_id = p.id
               )
        """,
        (grant,),
    )
    if cr.rowcount:
        _logger.warning(
            "faizy_core: granted %s free activities to %s customer(s) who had "
            "never received any and have never spent one.",
            grant,
            cr.rowcount,
        )
