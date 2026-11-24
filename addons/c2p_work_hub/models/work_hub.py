from odoo import api, fields, models

# Days ahead that counts as "due soon", and days of silence that counts as
# stale. Deliberately module constants rather than a settings record: the
# directive asks for configurable update policy, and that belongs to the policy
# engine in a later slice, not to a dashboard's reading of today.
DUE_SOON_DAYS = 7
STALE_DAYS = 3
RECENT_DAYS = 3
LIST_LIMIT = 40


class C2pWorkHub(models.AbstractModel):
    """Payload behind the My Work Today client action.

    One RPC returns every section, so the page renders in a single round trip.
    There is no stored aggregate anywhere: every number is read from
    project.task at request time, by the requesting user, under that user's own
    access rights. Nothing in this file elevates privileges, and that is deliberate — a
    personal work list must show exactly what its owner is allowed to see, so
    Odoo's record rules are the feature rather than an obstacle.
    """

    _name = "c2p.work.hub"
    _description = "C2P Work Hub data"

    TASK_FIELDS = [
        "name", "project_id", "stage_id", "date_deadline", "priority", "state",
        "user_ids", "c2p_last_update", "c2p_next_action",
    ]

    @api.model
    def get_data(self):
        Task = self.env["project.task"]
        today = fields.Date.context_today(self)
        closed = Task._c2p_closed_states()
        mine = [("user_ids", "in", self.env.uid)]
        open_only = [("state", "not in", closed)]
        base = mine + open_only

        soon = fields.Date.to_string(fields.Date.add(today, days=DUE_SOON_DAYS))
        stale_before = fields.Datetime.to_string(
            fields.Datetime.subtract(fields.Datetime.now(), days=STALE_DAYS))
        recent_after = fields.Datetime.to_string(
            fields.Datetime.subtract(fields.Datetime.now(), days=RECENT_DAYS))

        blocker_field = Task._c2p_blocker_field()
        task_fields = list(self.TASK_FIELDS)
        if blocker_field:
            task_fields.append(blocker_field)

        sections = {
            "today": {
                "label": "Due today",
                "domain": base + [("date_deadline", "=", today)],
            },
            "overdue": {
                "label": "Overdue",
                "domain": base + [("date_deadline", "<", today)],
            },
            "due_soon": {
                "label": "Due soon",
                "domain": base + [("date_deadline", ">", today),
                                  ("date_deadline", "<=", soon)],
            },
            "no_deadline": {
                "label": "No deadline set",
                "domain": base + [("date_deadline", "=", False)],
            },
            "stale": {
                "label": "Not updated recently",
                "domain": base + ["|",
                                  ("c2p_last_update", "=", False),
                                  ("c2p_last_update", "<", stale_before)],
            },
            "recently_assigned": {
                "label": "Recently assigned to me",
                "domain": base + [("create_date", ">=", recent_after)],
            },
        }

        out = {}
        for key, spec in sections.items():
            out[key] = self._read_section(spec["label"], spec["domain"],
                                          task_fields, blocker_field)

        # Blocked, waiting and review are stage-name matched, which no domain
        # can express, so they are filtered in Python over the user's open
        # tasks. Blocked and waiting are kept apart deliberately: "something is
        # stopping this and here is why" and "this sits with someone else" are
        # different situations needing different action, and the directive lists
        # them as separate sections. A task can legitimately be in both.
        open_tasks = self.env["project.task"].search(base, limit=200)
        blocked = open_tasks.filtered(
            lambda t: bool(blocker_field and t[blocker_field]))
        waiting = open_tasks.filtered(lambda t: t._c2p_is_waiting_stage())
        in_review = open_tasks.filtered(lambda t: t._c2p_is_review_stage())
        out["blocked"] = self._serialise(
            "Blocked", blocked[:LIST_LIMIT], task_fields,
            blocker_field, len(blocked))
        out["waiting_on_others"] = self._serialise(
            "Waiting on someone else", waiting[:LIST_LIMIT], task_fields,
            blocker_field, len(waiting))
        out["in_review"] = self._serialise(
            "With a reviewer", in_review[:LIST_LIMIT], task_fields,
            blocker_field, len(in_review))

        out["waiting_for_me"] = self._review_queue(task_fields, blocker_field,
                                                   closed)
        out["my_milestones"] = self._upcoming_milestones()
        out["my_projects"] = self._my_projects(base)
        out["states"] = self._state_choices()
        out["meta"] = {
            "user_name": self.env.user.name,
            "today": fields.Date.to_string(today),
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "has_blocker_field": bool(blocker_field),
            "stale_days": STALE_DAYS,
            "due_soon_days": DUE_SOON_DAYS,
        }
        return out

    # ── reading ─────────────────────────────────────────────────────────
    def _read_section(self, label, domain, task_fields, blocker_field):
        Task = self.env["project.task"]
        total = Task.search_count(domain)
        rows = Task.search_read(
            domain, task_fields, limit=LIST_LIMIT,
            order="date_deadline asc, priority desc, id desc")
        return {
            "label": label,
            "count": total,
            "truncated": total > len(rows),
            "tasks": [self._row(r, blocker_field) for r in rows],
            "action": {"res_model": "project.task", "domain": domain,
                       "name": label, "views": "list"},
        }

    def _serialise(self, label, tasks, task_fields, blocker_field, total):
        return {
            "label": label,
            "count": total,
            "truncated": total > len(tasks),
            "tasks": [self._row(r, blocker_field)
                      for r in tasks.read(task_fields)],
            "action": {"res_model": "project.task",
                       "domain": [("id", "in", tasks.ids)],
                       "name": label, "views": "list"},
        }

    def _row(self, record, blocker_field):
        """One task, flattened for the client. Many2one tuples become plain
        strings so the template never has to know Odoo's wire format."""
        def name_of(val):
            return val[1] if isinstance(val, (list, tuple)) and len(val) > 1 else ""

        return {
            "id": record["id"],
            "name": record.get("name") or "",
            "project": name_of(record.get("project_id")),
            "project_id": (record.get("project_id") or [False])[0]
            if isinstance(record.get("project_id"), (list, tuple)) else False,
            "stage": name_of(record.get("stage_id")),
            "deadline": record.get("date_deadline") or "",
            "priority": record.get("priority") or "0",
            "state": record.get("state") or "",
            "last_update": record.get("c2p_last_update") or "",
            "next_action": record.get("c2p_next_action") or "",
            "blocker": (record.get(blocker_field) or "") if blocker_field else "",
        }

    def _review_queue(self, task_fields, blocker_field, closed):
        """Work sitting with this user as a project manager, not as an assignee.

        Wave B's "manager review queue". It is deliberately derived from the
        project's manager field and a review-named stage, because formal
        approval records do not exist yet — approvals are a separate model in a
        later wave, and inventing a half version here would give the business a
        second answer later. Tasks the user is themselves assigned to are
        excluded: those are their own work and already appear above.
        """
        managed = self.env["project.project"].search(
            [("user_id", "=", self.env.uid)])
        if not managed:
            return {"label": "Waiting for my review", "count": 0,
                    "truncated": False, "tasks": [], "is_manager": False,
                    "action": {"res_model": "project.task", "domain": [("id", "in", [])],
                               "name": "Waiting for my review", "views": "list"}}

        candidates = self.env["project.task"].search([
            ("project_id", "in", managed.ids),
            ("state", "not in", closed),
            ("user_ids", "not in", self.env.uid),
        ], limit=200)
        queue = candidates.filtered(lambda t: t._c2p_is_review_stage())
        payload = self._serialise("Waiting for my review", queue[:LIST_LIMIT],
                                  task_fields, blocker_field, len(queue))
        payload["is_manager"] = True
        return payload

    def _upcoming_milestones(self):
        """Standard project.milestone records falling due soon.

        This repository carries three milestone notions: standard
        project.milestone (which c2p_project_tracker's hygiene constraint
        requires delivery tasks to reference), portfolio milestone *tasks*
        named "M1 ..." matched by name, and delivery_milestone_id pairing the
        two. The hub reads the standard model because it is the one with
        enforced data behind it, and because reading the name-matched tasks here
        would make this a fourth place that decides what a milestone is.
        Reconciling the three is an architecture decision, not a dashboard's.
        """
        Milestone = self.env["project.milestone"]
        today = fields.Date.context_today(self)
        horizon = fields.Date.to_string(fields.Date.add(today, days=30))
        mine = self.env["project.project"].search(["|",
                                                   ("user_id", "=", self.env.uid),
                                                   ("task_ids.user_ids", "in", self.env.uid)])
        if not mine:
            return []
        rows = Milestone.search_read(
            [("project_id", "in", mine.ids),
             ("is_reached", "=", False),
             ("deadline", "!=", False),
             ("deadline", "<=", horizon)],
            ["name", "project_id", "deadline"],
            limit=LIST_LIMIT, order="deadline asc")
        return [{"id": r["id"], "name": r.get("name") or "",
                 "project": (r["project_id"][1] if r.get("project_id") else ""),
                 "deadline": r.get("deadline") or "",
                 "overdue": bool(r.get("deadline") and r["deadline"] < today)}
                for r in rows]

    def _my_projects(self, base):
        """Projects the user has open work in, with their open-task counts."""
        groups = self.env["project.task"].read_group(
            base, ["id"], ["project_id"], lazy=False)
        rows = []
        for g in groups:
            proj = g.get("project_id")
            if not proj:
                continue
            rows.append({"id": proj[0], "name": proj[1],
                         "open_tasks": g.get("__count") or g.get("id_count") or 0})
        rows.sort(key=lambda r: -r["open_tasks"])
        return rows

    def _state_choices(self):
        """The status values a user may move a task to, open ones first."""
        Task = self.env["project.task"]
        closed = set(Task._c2p_closed_states())
        try:
            selection = Task._fields["state"].selection
        except Exception:
            return []
        return [{"value": k, "label": str(label), "closed": k in closed}
                for k, label in selection]
