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
        history = context.get("history", [])

        # Embed financial data in system prompt
        full_system = system_prompt
        if financial_data:
            full_system += (f"\n\n--- Real-time Financial Data for {company_name} ---\n"
                            f"{financial_data}\n--- End of Data ---")

        # Build messages with conversation history
        # Anthropic requires alternating user/assistant — enforce this
        messages = []
        for msg in history:
            role = msg["role"]
            if messages and messages[-1]["role"] == role:
                # Merge consecutive same-role messages
                messages[-1]["content"] += "\n" + msg["content"]
            else:
                messages.append({"role": role, "content": msg["content"]})

        # Add current user message
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n" + prompt
        else:
            messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                _ANTHROPIC_URL,
                headers={"x-api-key": api_key, "anthropic-version": _ANTHROPIC_VERSION,
                         "Content-Type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "system": full_system,
                      "messages": messages},
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
