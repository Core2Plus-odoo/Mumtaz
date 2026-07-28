from odoo import api, models


class ReportFinancial(models.AbstractModel):
    _name = "report.mumtaz_financial_reports.report_financial"
    _description = "Mumtaz Financial Statement Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env["mumtaz.financial.report.wizard"].browse(docids)
        wiz = wizards[:1]
        return {
            "doc_ids": docids,
            "doc_model": "mumtaz.financial.report.wizard",
            "docs": wizards,
            "report": wiz._compute_report() if wiz else {},
            "company": wiz.company_id,
        }
