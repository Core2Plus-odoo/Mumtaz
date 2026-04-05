from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from openai import AsyncOpenAI
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Transcribe voice to text using OpenAI Whisper."""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(503, "Voice service not configured")

    allowed = {"audio/webm", "audio/mp4", "audio/mpeg", "audio/wav", "audio/ogg"}
    if audio.content_type not in allowed:
        raise HTTPException(400, f"Unsupported audio format: {audio.content_type}")

    content = await audio.read()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=(audio.filename or "audio.webm", content, audio.content_type),
        language="en",
    )

    return {"text": transcript.text}
