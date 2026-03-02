import json

from odoo import models


class AIService(models.AbstractModel):
    _name = "mumtaz.ai.service"
    _description = "Mumtaz AI Service"

    def process_user_prompt(self, session, prompt):
        intent = self._detect_intent(prompt)
        company = session.company_id
        user = session.user_id

        response_data = self._route_intent(intent, prompt, company)
        self.env["mumtaz.ai.message"].create(
            {
                "session_id": session.id,
                "user_id": user.id,
                "company_id": company.id,
                "intent": intent,
                "prompt": prompt,
                "response": response_data["response"],
                "token_usage": response_data.get("token_usage", 0),
                "model_used": response_data.get("model_used", "router"),
                "execution_status": "done",
            }
        )

        self.env["mumtaz.core.log"].log_action(
            module_name="mumtaz_ai",
            action="process_user_prompt",
            company=company,
            user=user,
            request_payload=json.dumps({"prompt": prompt, "intent": intent}),
            response_payload=json.dumps(response_data),
            level="info",
        )
        return response_data

    def _detect_intent(self, prompt):
        prompt_lower = (prompt or "").lower()
        if any(keyword in prompt_lower for keyword in ["cash position", "bank balance", "liquidity"]):
            return "financial_query"
        if any(keyword in prompt_lower for keyword in ["lead", "opportunity", "pipeline", "crm"]):
            return "crm_query"
        if any(keyword in prompt_lower for keyword in ["sale", "quotation", "order", "revenue"]):
            return "sales_query"
        return "general_query"

    def _route_intent(self, intent, prompt, company):
        handlers = {
            "financial_query": self._handle_financial_query,
            "crm_query": self._handle_crm_query,
            "sales_query": self._handle_sales_query,
            "general_query": self._handle_general_query,
        }
        return handlers.get(intent, self._handle_general_query)(prompt, company)

    def _handle_financial_query(self, prompt, company):
        accounts = self.env["account.account"].search(
            [
                ("company_id", "=", company.id),
                ("account_type", "in", ["asset_cash", "liability_credit_card"]),
            ]
        )
        move_count = self.env["account.move"].search_count(
            [("company_id", "=", company.id), ("state", "=", "posted")]
        )
        total_balance = 0.0
        if accounts:
            group_data = self.env["account.move.line"].read_group(
                [
                    ("company_id", "=", company.id),
                    ("parent_state", "=", "posted"),
                    ("account_id", "in", accounts.ids),
                ],
                ["balance:sum"],
                [],
            )
            if group_data:
                total_balance = group_data[0].get("balance", 0.0)

        response = (
            f"Cash position summary for {company.name}: {total_balance:,.2f}. "
            f"Based on {len(accounts)} liquidity accounts and {move_count} posted journal entries."
        )
        return {"response": response, "model_used": "financial_router", "token_usage": 0}

    def _handle_crm_query(self, prompt, company):
        return {
            "response": f"CRM insight routing is enabled for {company.name}. Add domain-specific handlers next.",
            "model_used": "crm_router",
            "token_usage": 0,
        }

    def _handle_sales_query(self, prompt, company):
        return {
            "response": f"Sales insight routing is enabled for {company.name}. Add domain-specific handlers next.",
            "model_used": "sales_router",
            "token_usage": 0,
        }

    def _handle_general_query(self, prompt, company):
        provider = self.env["mumtaz.ai.provider.base"]
        return provider.generate_response(prompt=prompt, context={"company_id": company.id})
