import base64
import logging

import requests as req

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
_TTS_TIMEOUT = 30


class MumtazVoiceController(http.Controller):

    @http.route("/mumtaz/voice/query", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def voice_query(self, transcript, session_id=None, language="en", **kwargs):
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
            session.with_context(voice_language=language).action_ask()
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

    @http.route("/mumtaz/voice/tts", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def voice_tts(self, text, language="en", **kwargs):
        text = (text or "").strip()[:4000]
        if not text:
            return {"error": "Empty text"}
        try:
            settings = request.env["mumtaz.core.settings"].sudo().search(
                [("company_id", "=", request.env.company.id), ("active", "=", True)], limit=1
            )
            if not settings:
                return {"error": "No settings configured"}

            provider = getattr(settings, "tts_provider", None) or "openai"
            if provider == "elevenlabs":
                return self._tts_elevenlabs(text, settings)
            return self._tts_openai(text, settings)
        except req.exceptions.Timeout:
            return {"error": "TTS request timed out"}
        except Exception as exc:
            _logger.warning("Mumtaz TTS failed: %s", exc)
            return {"error": str(exc)}

    def _tts_openai(self, text, settings):
        if not settings.api_key:
            return {"error": "No OpenAI API key configured"}
        voice = getattr(settings, "tts_voice", None) or "nova"
        tts_model = getattr(settings, "tts_model", None) or "tts-1"
        resp = req.post(
            _OPENAI_TTS_URL,
            headers={"Authorization": f"Bearer {settings.api_key}",
                     "Content-Type": "application/json"},
            json={"model": tts_model, "input": text, "voice": voice, "response_format": "mp3"},
            timeout=_TTS_TIMEOUT,
        )
        resp.raise_for_status()
        return {"audio": base64.b64encode(resp.content).decode(), "format": "mp3"}

    def _tts_elevenlabs(self, text, settings):
        el_key = getattr(settings, "elevenlabs_api_key", None)
        if not el_key:
            return {"error": "No ElevenLabs API key configured"}
        voice_id = getattr(settings, "elevenlabs_voice_id", None) or "21m00Tcm4TlvDq8ikWAM"
        model_id = getattr(settings, "elevenlabs_model", None) or "eleven_multilingual_v2"
        resp = req.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": el_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": model_id,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=_TTS_TIMEOUT,
        )
        resp.raise_for_status()
        return {"audio": base64.b64encode(resp.content).decode(), "format": "mp3"}

    @http.route("/mumtaz/voice/session/<int:session_id>/history", type="jsonrpc", auth="user", methods=["GET"])
    def session_history(self, session_id, **kwargs):
        session = request.env["mumtaz.voice.session"].browse(session_id)
        if not session.exists():
            return {"error": "Session not found."}
        messages = []
        for msg in session.voice_message_ids.sorted(key="create_date"):
            messages.append({
                "role": msg.role, "content": msg.content, "intent": msg.intent or "",
                "model_used": msg.model_used or "",
                "timestamp": msg.create_date.strftime("%Y-%m-%d %H:%M:%S") if msg.create_date else "",
            })
        return {"session_id": session_id, "messages": messages}
