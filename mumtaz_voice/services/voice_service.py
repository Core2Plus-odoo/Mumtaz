import json

from odoo import models
from odoo.exceptions import UserError


CFO_SYSTEM_PROMPT = """You are Mumtaz, an AI CFO Assistant integrated directly into the company's ERP system.

Your role:
- Analyze real-time financial data pulled directly from the company's Odoo database
- Answer questions concisely and professionally, as a seasoned CFO would
- Highlight key metrics, trends, risks, and actionable insights
- Use exact numbers from the provided data — never fabricate figures
- Keep responses focused: 2-5 sentences unless a detailed breakdown is requested
- When data is missing or unavailable, say so clearly

Tone: Direct, authoritative, and business-focused. Speak as if briefing the board.
"""


class VoiceService(models.AbstractModel):
    _name = "mumtaz.voice.service"
    _description = "Mumtaz Voice Assistant Orchestration Service"

    def process_cfo_query(self, session, transcript):
        company = session.company_id
        user = session.user_id
        settings = self._get_settings(company)
        self._ensure_voice_enabled(settings)

        intent = self.env["mumtaz.cfo.service"].detect_intent(transcript)
        financial_context = self.env["mumtaz.cfo.service"].build_financial_context(company, intent)
        response_data = self._call_ai_provider(settings=settings, transcript=transcript,
                                               financial_context=financial_context, company=company)
        response_data["intent"] = intent
        response_data["financial_context"] = financial_context

        self.env["mumtaz.voice.message"].create({
            "session_id": session.id, "company_id": company.id, "user_id": user.id,
            "role": "user", "content": transcript, "intent": intent,
        })
        self.env["mumtaz.voice.message"].create({
            "session_id": session.id, "company_id": company.id, "user_id": user.id,
            "role": "assistant", "content": response_data.get("response", ""),
            "intent": intent, "model_used": response_data.get("model_used"),
            "token_usage": response_data.get("token_usage", 0),
        })
        self.env["mumtaz.core.log"].log_action(
            module_name="mumtaz_voice", action="cfo_voice_query", company=company, user=user,
            request_payload=json.dumps({"transcript": transcript, "intent": intent,
                                        "tenant": settings.tenant_code}, default=str),
            response_payload=json.dumps({"model_used": response_data.get("model_used"),
                                         "token_usage": response_data.get("token_usage", 0)}, default=str),
            level="info",
        )
        return response_data

    def _get_settings(self, company):
        settings = self.env["mumtaz.core.settings"].search(
            [("company_id", "=", company.id), ("active", "=", True)], limit=1
        )
        if not settings:
            raise UserError(f"No active Mumtaz settings found for {company.display_name}. "
                            "Please configure Mumtaz Core Settings first.")
        return settings

    def _ensure_voice_enabled(self, settings):
        if not settings.feature_voice_enabled:
            raise UserError(f"Voice Assistant is disabled for tenant {settings.tenant_code}. "
                            "Enable it in Mumtaz Settings \u2192 Feature Toggles.")

    def _call_ai_provider(self, settings, transcript, financial_context, company):
        provider_name = settings.ai_provider
        if provider_name == "openai":
            provider = self.env["mumtaz.ai.provider.openai"]
        elif provider_name == "anthropic":
            provider = self.env["mumtaz.ai.provider.anthropic"]
        else:
            return self._fallback_response(financial_context, company)
        context = {
            "api_key": settings.api_key,
            "company_name": company.name,
            "financial_data": financial_context,
            "system_prompt": CFO_SYSTEM_PROMPT,
            "max_tokens": settings.max_tokens_per_request,
            "model": getattr(settings, "openai_model", "gpt-4o-mini") if provider_name == "openai" else None,
        }
        return provider.generate_response(prompt=transcript, context=context)

    def _fallback_response(self, financial_context, company):
        return {
            "response": (f"Here is the current financial data for {company.name}:\n\n"
                         f"{financial_context}\n"
                         "Note: Configure an AI provider (OpenAI or Anthropic) in Mumtaz Settings "
                         "to receive natural-language CFO analysis."),
            "model_used": "fallback_router",
            "token_usage": 0,
        }
