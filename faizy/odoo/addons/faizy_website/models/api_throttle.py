from datetime import timedelta

from odoo import api, fields, models


class FaizyApiThrottle(models.Model):
    """One row per attempt on an anonymous API route, so attempts can be counted.

    Kept in the database rather than in memory because Odoo runs several
    worker processes: a counter in one worker does not see the requests the
    others served. Rows older than a day are removed by the daily autovacuum.
    Only ever touched with sudo() from the controller; no user needs access.
    """

    _name = "faizy.api.throttle"
    _description = "Faizy API attempt (rate limiting)"
    _order = "id desc"

    scope = fields.Char(required=True, index=True)
    key = fields.Char(required=True, index=True)

    @api.model
    def allow(self, scope, key, limit, minutes):
        """Record an attempt and say whether it is within `limit` per `minutes`.

        The attempt is recorded before counting, so refused attempts keep the
        caller blocked until they actually stop.
        """
        self.create({"scope": scope, "key": key or "unknown"})
        since = fields.Datetime.now() - timedelta(minutes=minutes)
        count = self.search_count([
            ("scope", "=", scope),
            ("key", "=", key or "unknown"),
            ("create_date", ">=", since),
        ])
        return count <= limit

    @api.autovacuum
    def _gc_attempts(self):
        self.search([
            ("create_date", "<", fields.Datetime.now() - timedelta(days=1)),
        ]).unlink()
