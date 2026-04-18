from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext
from anthropic import Anthropic
from dotenv import load_dotenv
import sqlite3, os, json, time

load_dotenv()

app = FastAPI(title="ZAKI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://zaki.mumtaz.digital", "https://app.mumtaz.digital", "http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH    = os.environ.get("DB_PATH", "/opt/zaki-server/users.db")
SECRET     = os.environ.get("JWT_SECRET", "change-me-in-production")
ALGO       = "HS256"
TOKEN_DAYS = 30
ANT_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            tenant        TEXT    NOT NULL DEFAULT 'mumtaz',
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
    """)
    conn.commit()
    conn.close()


def make_token(user_id: int, email: str) -> str:
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": int(time.time()) + 86400 * TOKEN_DAYS},
        SECRET, ALGO
    )


async def require_auth(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    try:
        return jwt.decode(authorization.split(" ", 1)[1], SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(401, f"Token invalid: {e}")


class LoginReq(BaseModel):
    email: str
    password: str


class ChatReq(BaseModel):
    message: str
    session_id: str | None = None


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "ai_ready": bool(ANT_KEY)}


@app.post("/api/v1/auth/login")
def login(req: LoginReq):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ? AND active = 1",
        (req.email.strip().lower(),)
    ).fetchone()
    conn.close()
    if not row or not pwd_ctx.verify(req.password, row["password_hash"]):
        raise HTTPException(401, detail="Invalid email or password")
    token = make_token(row["id"], row["email"])
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/v1/ai/chat/stream")
async def chat_stream(req: ChatReq, user: dict = Depends(require_auth)):
    if not ANT_KEY:
        raise HTTPException(503, "AI service not configured on server — contact admin")

    client = Anthropic(api_key=ANT_KEY)

    async def generate():
        try:
            with client.messages.stream(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'text': f'[Server error: {e}]'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
