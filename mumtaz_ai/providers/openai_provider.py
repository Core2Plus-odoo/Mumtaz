import logging

import requests

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_REQUEST_TIMEOUT = 45


class OpenAIProvider(models.AbstractModel):
    _name = "mumtaz.ai.provider.openai"
    _inherit = "mumtaz.ai.provider.base"
    _description = "Mumtaz OpenAI Provider (GPT-4o / GPT-4o-mini)"

    def generate_response(self, prompt, context=None):
        context = context or {}
        api_key = context.get("api_key", "")
        if not api_key:
            return {"response": ("OpenAI API key is not configured. "
                                 "Please add your key in Mumtaz AI \u2192 Configuration \u2192 Settings."),
                    "model_used": "openai-unconfigured", "token_usage": 0}

        system_prompt = context.get("system_prompt", "You are a helpful AI assistant.")
        financial_data = context.get("financial_data", "")
        company_name = context.get("company_name", "")
        model = context.get("model") or _DEFAULT_MODEL
        max_tokens = int(context.get("max_tokens") or 600)
        history = context.get("history", [])

        # Embed financial data in the system prompt so it's available for all turns
        full_system = system_prompt
        if financial_data:
            full_system += (f"\n\n--- Real-time Financial Data for {company_name} ---\n"
                            f"{financial_data}\n--- End of Data ---")

        messages = [{"role": "system", "content": full_system}]

        # Inject conversation history
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Current user message
        messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                _OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3},
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "response": data["choices"][0]["message"]["content"].strip(),
                "model_used": data.get("model", model),
                "token_usage": data.get("usage", {}).get("total_tokens", 0),
            }
        except requests.exceptions.Timeout:
            raise UserError("OpenAI API request timed out. Please try again.")
        except requests.exceptions.HTTPError as exc:
            try:
                err_msg = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                err_msg = str(exc)
            raise UserError(f"OpenAI API error: {err_msg}")
        except requests.exceptions.RequestException as exc:
            raise UserError(f"OpenAI connection error: {exc}")
