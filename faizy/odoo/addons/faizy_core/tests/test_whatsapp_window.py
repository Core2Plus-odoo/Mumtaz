from datetime import datetime
from unittest.mock import patch

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

SEND = "odoo.addons.faizy_core.models.faizy_whatsapp_transport.ResCompanyWhatsApp._send_whatsapp"
NOW = "odoo.fields.Datetime.now"

# Karachi is UTC+5 all year: 10:00 there is 05:00 UTC, 21:00 is 16:00 UTC.
INSIDE = datetime(2026, 11, 23, 8, 0)    # 13:00 Karachi
BEFORE = datetime(2026, 11, 23, 4, 59)   # 09:59 Karachi
AFTER = datetime(2026, 11, 23, 16, 0)    # 21:00 Karachi
NIGHT = datetime(2026, 11, 23, 21, 30)   # 02:30 Karachi next day


@tagged("post_install", "-at_install", "faizy")
class TestWhatsappSendWindow(TransactionCase):
    """Customer messages leave between 10:00 and 21:00 Karachi time, nothing else is held."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Message = cls.env["faizy.whatsapp.message"]
        cls.partner = mail_new_test_user(
            cls.env, login="wa_window_cust", name="Window Customer", groups="base.group_portal"
        ).partner_id
        cls.worker = cls.env["faizy.worker"].create(
            {"name": "Window Worker", "phone": "+923001234567", "city": "Karachi"}
        )
        # HQ05: sending is off unless this parameter says "on"; the window sits behind it.
        cls.env["ir.config_parameter"].sudo().set_param("faizy.whatsapp_send_mode", "on")
        company = cls.env.company
        company.write({
            "faizy_whatsapp_provider": "meta",
            "faizy_whatsapp_meta_token": "TEST-TOKEN",
            "faizy_whatsapp_meta_phone_id": "TEST-PHONE-ID",
        })

    def _msg(self, message_type="status_update", **extra):
        values = {"phone": "+923001234567", "message_type": message_type, "body": "Faizy test"}
        values.update(extra)
        return self.Message.create(values)

    def test_window_edges_in_karachi_time(self):
        for when, expected in ((BEFORE, False), (datetime(2026, 11, 23, 5, 0), True),
                               (INSIDE, True), (datetime(2026, 11, 23, 15, 59), True),
                               (AFTER, False), (NIGHT, False)):
            self.assertEqual(self.Message._within_send_hours(when), expected, when)

    def test_window_can_be_changed_with_parameters(self):
        self.env["ir.config_parameter"].sudo().set_param("faizy.send_hours_start", "12")
        self.assertFalse(self.Message._within_send_hours(datetime(2026, 11, 23, 5, 0)))  # 10:00 Karachi
        self.assertTrue(self.Message._within_send_hours(datetime(2026, 11, 23, 7, 0)))   # 12:00 Karachi

    def test_customer_message_is_held_outside_the_window(self):
        message = self._msg(partner_id=self.partner.id)
        with patch(NOW, return_value=NIGHT), patch(SEND, return_value={"message_id": "x"}) as send:
            message.action_send()
        send.assert_not_called()
        self.assertEqual(message.state, "queued")
        self.assertEqual(message.attempts, 0, "a held message is not a failed attempt")
        self.assertIn("Held until", message.error_message)

    def test_customer_message_goes_out_inside_the_window(self):
        message = self._msg(partner_id=self.partner.id)
        with patch(NOW, return_value=INSIDE), patch(SEND, return_value={"message_id": "x"}) as send:
            message.action_send()
        send.assert_called_once()
        self.assertEqual(message.state, "sent")

    def test_held_message_is_sent_once_the_window_opens(self):
        message = self._msg(partner_id=self.partner.id)
        with patch(NOW, return_value=NIGHT), patch(SEND, return_value={"message_id": "x"}):
            message.action_send()
        self.assertEqual(message.state, "queued")
        with patch(NOW, return_value=INSIDE), patch(SEND, return_value={"message_id": "x"}):
            message.action_send()
        self.assertEqual(message.state, "sent")
        self.assertFalse(message.error_message)

    def test_login_code_and_worker_messages_are_not_held(self):
        otp = self._msg("otp", partner_id=self.partner.id)
        job = self._msg("worker_assignment", worker_id=self.worker.id)
        with patch(NOW, return_value=NIGHT), patch(SEND, return_value={"message_id": "x"}) as send:
            (otp | job).action_send()
        self.assertEqual(send.call_count, 2)
        self.assertEqual((otp | job).mapped("state"), ["sent", "sent"])

    def test_cron_leaves_held_rows_alone_outside_the_window(self):
        held = self._msg(partner_id=self.partner.id)
        job = self._msg("worker_assignment", worker_id=self.worker.id)
        with patch(NOW, return_value=NIGHT), patch(SEND, return_value={"message_id": "x"}):
            self.Message._cron_send_queued()
        self.assertEqual(held.state, "queued")
        self.assertFalse(held.error_message, "not even rewritten every 15 minutes")
        self.assertEqual(job.state, "sent")

    def test_nothing_is_sent_while_no_provider_is_configured(self):
        self.env.company.faizy_whatsapp_provider = "none"
        message = self._msg(partner_id=self.partner.id)
        with patch(NOW, return_value=INSIDE), patch(SEND, return_value={"message_id": "x"}) as send:
            message.action_send()
        send.assert_not_called()
        self.assertEqual(message.state, "queued")

    def test_send_switch_off_beats_the_window(self):
        self.env["ir.config_parameter"].sudo().set_param("faizy.whatsapp_send_mode", "off")
        message = self._msg(partner_id=self.partner.id)
        self.assertEqual(message.state, "held")
        with patch(NOW, return_value=INSIDE), patch(SEND, return_value={"message_id": "x"}) as send:
            with self.assertRaises(UserError):
                message.action_send()
            self.Message._cron_send_queued()
        send.assert_not_called()
        self.assertEqual(message.state, "held")
