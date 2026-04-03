from odoo import api, fields, models


class MumtazSubscriptionNotificationService(models.AbstractModel):
    _name = "mumtaz.subscription.notification.service"
    _description = "Mumtaz Subscription Notification Service"

    @api.model
    def _notification_policy(self):
        params = self.env["ir.config_parameter"].sudo()
        trial_days = int(params.get_param("mumtaz_control_plane.notifications.trial_ending_days", 3))
        grace_days = int(params.get_param("mumtaz_control_plane.notifications.grace_ending_days", 2))
        send_email = str(params.get_param("mumtaz_control_plane.notifications.send_email", "false")).lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        return {
            "trial_ending_days": trial_days,
            "grace_ending_days": grace_days,
            "send_email": send_email,
        }

    def _target_partners(self, subscription):
        partners = self.env["res.partner"]
        tenant = subscription.tenant_id

        if tenant.partner_id:
            partners |= tenant.partner_id
            partners |= tenant.partner_id.user_ids.mapped("partner_id")

        admin_groups = [
            "mumtaz_control_plane.group_mumtaz_super_admin",
            "mumtaz_control_plane.group_mumtaz_billing_admin",
            "mumtaz_control_plane.group_mumtaz_tenant_admin",
        ]
        for group_xmlid in admin_groups:
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                partners |= group.users.mapped("partner_id")

        return partners.filtered(lambda p: p)

    @api.model
    def _event_message(self, subscription, event_code):
        payload = {
            "trial_ending_soon": (
                "Trial ending soon",
                f"Trial for {subscription.display_name} ends on {subscription.trial_end}.",
            ),
            "payment_overdue": (
                "Payment overdue",
                f"Payment is overdue for {subscription.display_name}; status is {subscription.status}.",
            ),
            "entered_grace": (
                "Grace period started",
                f"{subscription.display_name} is now in grace until {subscription.grace_until}.",
            ),
            "grace_ending_soon": (
                "Grace ending soon",
                f"Grace for {subscription.display_name} ends on {subscription.grace_until}.",
            ),
            "suspended": (
                "Subscription suspended",
                f"{subscription.display_name} has been suspended.",
            ),
            "reactivated": (
                "Subscription reactivated",
                f"{subscription.display_name} has been reactivated.",
            ),
            "renewal_requested": (
                "Renewal requested",
                f"Renewal workflow requested for {subscription.display_name}.",
            ),
        }
        return payload.get(event_code, ("Subscription update", f"Subscription event: {event_code}"))

    @api.model
    def _send(self, subscription, event_code, dedupe_key, source="manual"):
        NotificationLog = self.env["mumtaz.subscription.notification.log"].sudo()
        existing = NotificationLog.search(
            [
                ("subscription_id", "=", subscription.id),
                ("event_code", "=", event_code),
                ("dedupe_key", "=", dedupe_key),
            ],
            limit=1,
        )
        if existing:
            return False

        title, body = self._event_message(subscription, event_code)
        partners = self._target_partners(subscription)
        policy = self._notification_policy()

        if subscription.tenant_id:
            subscription.tenant_id.message_post(
                subject=title,
                body=body,
                partner_ids=partners.ids,
            )

        email_sent = False
        if policy["send_email"]:
            emails = [p.email for p in partners if p.email]
            if emails:
                self.env["mail.mail"].sudo().create(
                    {
                        "subject": title,
                        "body_html": f"<p>{body}</p>",
                        "email_to": ",".join(emails),
                    }
                ).send()
                email_sent = True

        NotificationLog.create(
            {
                "subscription_id": subscription.id,
                "tenant_id": subscription.tenant_id.id,
                "event_code": event_code,
                "dedupe_key": dedupe_key,
                "channel_chatter": True,
                "channel_internal": bool(partners),
                "channel_email": email_sent,
                "source": source,
            }
        )
        return True

    @api.model
    def notify_event(self, subscription, event_code, source="manual"):
        today = fields.Date.context_today(self)
        dedupe_key = f"{event_code}:{today}"
        return self._send(subscription, event_code, dedupe_key, source=source)

    @api.model
    def notify_transition(self, subscription, from_status, to_status, source="lifecycle"):
        mapping = {
            "grace": "entered_grace",
            "suspended": "suspended",
            "active": "reactivated",
        }
        event = mapping.get(to_status)
        if not event:
            return False
        dedupe_key = f"transition:{from_status}:{to_status}:{fields.Date.context_today(self)}"
        return self._send(subscription, event, dedupe_key, source=source)

    @api.model
    def cron_dispatch_notifications(self):
        today = fields.Date.context_today(self)
        policy = self._notification_policy()
        subscriptions = self.env["mumtaz.subscription"].search(
            [("status", "in", ["trial", "active", "past_due", "grace", "suspended"])]
        )

        for sub in subscriptions:
            if sub.status == "trial" and sub.trial_end:
                remaining = (sub.trial_end - today).days
                if 0 <= remaining <= policy["trial_ending_days"]:
                    self._send(sub, "trial_ending_soon", f"trial:{sub.trial_end}", source="cron")

            if sub.payment_status == "overdue" and sub.status in ("active", "past_due", "grace"):
                self._send(sub, "payment_overdue", f"overdue:{today}", source="cron")

            if sub.status == "grace" and sub.grace_until:
                remaining = (sub.grace_until - today).days
                if 0 <= remaining <= policy["grace_ending_days"]:
                    self._send(sub, "grace_ending_soon", f"grace-ending:{sub.grace_until}", source="cron")

        return True
