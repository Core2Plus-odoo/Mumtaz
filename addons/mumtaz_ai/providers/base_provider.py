from odoo import models


class BaseAIProvider(models.AbstractModel):
    _name = "mumtaz.ai.provider.base"
    _description = "Base Mumtaz AI Provider"

    def generate_response(self, prompt, context=None):
        """Return provider response payload.

        Provider implementations should return a dict:
        {
            'response': str,
            'model_used': str,
            'token_usage': int,
        }
        """
        return {
            "response": "Provider not configured. Configure a provider in Mumtaz settings.",
            "model_used": "none",
            "token_usage": 0,
        }
