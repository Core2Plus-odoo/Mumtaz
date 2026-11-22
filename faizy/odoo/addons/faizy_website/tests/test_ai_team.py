import os

from odoo.addons.faizy_website.ai_team_data import AI_TEAM_GROUPS
from odoo.tests.common import HttpCase, tagged

STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "src")


@tagged("post_install", "-at_install")
class TestAITeamPage(HttpCase):

    def test_every_agent_has_a_portrait_and_a_voice_clip(self):
        keys = [a["key"] for g in AI_TEAM_GROUPS for a in g["agents"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 9)
        for key in keys:
            self.assertTrue(os.path.exists(os.path.join(STATIC, "img", "ai-team", key + ".jpg")), key)
            self.assertTrue(os.path.exists(os.path.join(STATIC, "audio", "ai-team", key + ".mp3")), key)

    def test_page_renders_labelled_agents(self):
        response = self.url_open("/ai-team")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertEqual(html.count('class="fz-agent-voice"'), 9)
        self.assertEqual(html.count("fz-agent-badge"), 9)
        self.assertIn("Every agent here is labelled AI", html)
        self.assertIn("Portraits are AI-generated", html)

    def test_no_stale_whatsapp_number_on_the_page(self):
        html = self.url_open("/ai-team").text
        for stale in ("0334 272 6048", "335 3043972", "3353043972"):
            self.assertNotIn(stale, html)
