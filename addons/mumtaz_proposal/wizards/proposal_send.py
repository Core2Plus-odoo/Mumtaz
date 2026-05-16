from odoo import api, fields, models, _


class MumtazProposalSend(models.TransientModel):
    _name = "mumtaz.proposal.send"
    _description = "Send Proposal by Email"

    proposal_id = fields.Many2one(
        "mumtaz.proposal",
        string="Proposal",
        required=True,
    )
    partner_ids = fields.Many2many(
        "res.partner",
        string="Recipients",
    )
    subject = fields.Char(string="Subject", required=True)
    body_html = fields.Html(string="Message Body")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        proposal_id = self.env.context.get("default_proposal_id")
        if proposal_id:
            proposal = self.env["mumtaz.proposal"].browse(proposal_id)
            company = proposal.company_id
            res["proposal_id"] = proposal.id
            res["partner_ids"] = [proposal.partner_id.id] if proposal.partner_id else []
            res["subject"] = _("Proposal %s from %s") % (proposal.name, company.name)
            res["body_html"] = self._default_body(proposal)
        return res

    @api.model
    def _default_body(self, proposal):
        return """
<p>Dear %s,</p>
<p>Please find attached our proposal <strong>%s</strong> dated %s.</p>
<p>This proposal is valid until %s.</p>
<p>Please do not hesitate to contact us should you have any questions.</p>
<p>Kind regards,<br/>%s</p>
""" % (
            proposal.partner_id.name or "Valued Customer",
            proposal.name,
            proposal.date_proposal or "",
            proposal.date_valid or "—",
            proposal.user_id.name or proposal.company_id.name,
        )

    def action_send_email(self):
        self.ensure_one()
        proposal = self.proposal_id

        # Generate PDF attachment
        report = self.env.ref("mumtaz_proposal.action_report_proposal")
        pdf_content, mime_type = report._render_qweb_pdf([proposal.id])
        attachment = self.env["ir.attachment"].create(
            {
                "name": "%s.pdf" % proposal.name,
                "type": "binary",
                "datas": pdf_content,
                "res_model": "mumtaz.proposal",
                "res_id": proposal.id,
                "mimetype": "application/pdf",
            }
        )

        # Compose and send mail
        mail_values = {
            "subject": self.subject,
            "body_html": self.body_html,
            "author_id": self.env.user.partner_id.id,
            "email_from": self.env.user.email_formatted,
            "recipient_ids": [(4, pid) for pid in self.partner_ids.ids],
            "attachment_ids": [(4, attachment.id)],
            "auto_delete": False,
        }
        mail = self.env["mail.mail"].create(mail_values)
        mail.send()

        # Mark proposal as sent
        proposal.action_mark_sent()

        # Post message in chatter
        proposal.message_post(
            body=_("Proposal sent to: %s") % ", ".join(self.partner_ids.mapped("name")),
            attachment_ids=[attachment.id],
        )

        return {"type": "ir.actions.act_window_close"}
