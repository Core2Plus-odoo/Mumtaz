import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MumtazVoiceController(http.Controller):

    @http.route("/mumtaz/voice/query", type="json", auth="user", methods=["POST"], csrf=False)
    def voice_query(self, transcript, session_id=None, **kwargs):
        transcript = (transcript or "").strip()
        if not transcript:
            return {"error": "Empty query. Please speak or type your question."}
        try:
            session = None
            if session_id:
                session = request.env["mumtaz.voice.session"].browse(int(session_id))
                if not session.exists():
                    session = None
            if not session:
                session = request.env["mumtaz.voice.session"].create(
                    {"name": f"Voice Session \u2013 {request.env.user.name}", "transcript": transcript}
                )
            else:
                session.transcript = transcript
            session.action_ask()
            return {
                "session_id": session.id,
                "response": session.response or "",
                "intent": session.intent or "general",
                "model_used": session.model_used or "",
                "token_usage": session.token_usage or 0,
            }
        except Exception as exc:
            _logger.exception("Mumtaz Voice query failed: %s", exc)
            return {"error": str(exc)}

    @http.route("/mumtaz/voice/session/<int:session_id>/history", type="json", auth="user", methods=["GET"])
    def session_history(self, session_id, **kwargs):
        session = request.env["mumtaz.voice.session"].browse(session_id)
        if not session.exists():
            return {"error": "Session not found."}
        messages = []
        for msg in session.message_ids:
            messages.append({
                "role": msg.role, "content": msg.content, "intent": msg.intent or "",
                "model_used": msg.model_used or "",
                "timestamp": msg.create_date.strftime("%Y-%m-%d %H:%M:%S") if msg.create_date else "",
            })
        return {"session_id": session_id, "messages": messages}
