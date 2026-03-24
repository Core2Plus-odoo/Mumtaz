import logging

import requests

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_REQUEST_TIMEOUT = 45


class AnthropicProvider(models.AbstractModel):
    _name = "mumtaz.ai.provider.anthropic"
    _inherit = "mumtaz.ai.provider.base"
    _description = "Mumtaz Anthropic Provider (Claude)"

    def generate_response(self, prompt, context=None):
        context = context or {}
        api_key = context.get("api_key", "")
        if not api_key:
            return {"response": ("Anthropic API key is not configured. "
                                 "Please add your key in Mumtaz AI \u2192 Configuration \u2192 Settings."),
                    "model_used": "anthropic-unconfigured", "token_usage": 0}

        system_prompt = context.get("system_prompt", "You are a helpful AI assistant.")
        financial_data = context.get("financial_data", "")
        company_name = context.get("company_name", "")
        model = context.get("model") or _DEFAULT_MODEL
        max_tokens = int(context.get("max_tokens") or 600)

        user_content = prompt
        if financial_data:
            user_content = (f"Company: {company_name}\n\n"
                            f"--- Real-time Financial Data ---\n{financial_data}\n"
                            f"--- End of Data ---\n\nQuestion: {prompt}")

        try:
            resp = requests.post(
                _ANTHROPIC_URL,
                headers={"x-api-key": api_key, "anthropic-version": _ANTHROPIC_VERSION,
                         "Content-Type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "system": system_prompt,
                      "messages": [{"role": "user", "content": user_content}]},
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            usage = data.get("usage", {})
            return {
                "response": text.strip(),
                "model_used": data.get("model", model),
                "token_usage": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }
        except requests.exceptions.Timeout:
            raise UserError("Anthropic API request timed out. Please try again.")
        except requests.exceptions.HTTPError as exc:
            try:
                err_msg = exc.response.json().get("error", {}).get("message", str(exc))
            except Exception:
                err_msg = str(exc)
            raise UserError(f"Anthropic API error: {err_msg}")
        except requests.exceptions.RequestException as exc:
            raise UserError(f"Anthropic connection error: {exc}")
