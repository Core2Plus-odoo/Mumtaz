from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import httpx

from app.db.database import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    company: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        name=req.name,
        company=req.company,
        hashed_password=hash_password(req.password),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": _user_dict(user)}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": _user_dict(user)}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


# ── Odoo SSO ──────────────────────────────────────────────────────────────────

class OdooSSORequest(BaseModel):
    odoo_url: str          # e.g. https://app.mumtaz.digital
    api_key: str           # user's Odoo API key


@router.post("/sso/odoo", response_model=TokenResponse)
async def odoo_sso(req: OdooSSORequest, db: Session = Depends(get_db)):
    """Authenticate via Mumtaz ERP API key."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{req.odoo_url.rstrip('/')}/api/mumtaz/v1/health",
                headers={"X-API-Key": req.api_key},
                timeout=10,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Mumtaz ERP credentials")

            # Try to get user info
            user_resp = await client.get(
                f"{req.odoo_url.rstrip('/')}/web/session/get_session_info",
                headers={"X-API-Key": req.api_key},
                timeout=10,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Cannot reach Mumtaz ERP")

    # Upsert user
    odoo_email = req.api_key[:8] + "@erp.sso"  # fallback — real impl extracts from session
    user = db.query(User).filter(User.erp_api_key == req.api_key).first()
    if not user:
        user = User(
            email=odoo_email,
            name="ERP User",
            erp_api_key=req.api_key,
            odoo_instance_url=req.odoo_url,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": _user_dict(user)}


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "has_erp": bool(user.erp_api_key or user.odoo_access_token),
        "erp_url": user.odoo_instance_url,
    }
