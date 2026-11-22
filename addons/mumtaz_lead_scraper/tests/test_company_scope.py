"""Scraper jobs and the records they produce stay in their company."""
from odoo.tests import tagged

from .common import TwoCompanyCase


@tagged("post_install", "-at_install")
class TestScraperCompanyScope(TwoCompanyCase):
    GROUPS = ["mumtaz_lead_scraper.group_lead_scraper_user"]
    LOGIN_PREFIX = "scraper_scope"

    def test_jobs_and_records_stay_in_their_company(self):
        env = self.env(user=self.user_a)
        source = env["lead.scraper.source"].create({"name": "TEST Source", "url": "https://example.test/list"})
        job = env["lead.scraper.job"].create({"source_id": source.id})
        record = env["lead.scraper.record"].create({"job_id": job.id, "source_id": source.id, "company_name": "TEST Co"})
        self.assertEqual(job.sudo().company_id, self.company_a)
        self.assertEqual(record.sudo().company_id, self.company_a)
        self.assertHiddenFromB(job.sudo())
        self.assertHiddenFromB(record.sudo())
        self.assertHiddenFromB(source.sudo())
