from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.db.database import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.odoo.client import authenticate as odoo_authenticate

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


# ── Odoo Login ────────────────────────────────────────────────────────────────

class OdooLoginRequest(BaseModel):
    odoo_url: str
    db: str
    email: str
    password: str


@router.post("/sso/odoo", response_model=TokenResponse)
async def odoo_sso(req: OdooLoginRequest, db: Session = Depends(get_db)):
    """Authenticate directly against any Odoo instance via JSON-RPC."""
    base_url = req.odoo_url.rstrip("/")
    try:
        odoo = await odoo_authenticate(base_url, req.db, req.email, req.password)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    # Upsert user — key on (odoo_instance_url + odoo_user_id) so the same
    # Odoo account always maps to the same ZAKI user.
    uid_str = str(odoo["uid"])
    user = (
        db.query(User)
        .filter(User.odoo_instance_url == base_url, User.odoo_user_id == uid_str)
        .first()
    )
    if not user:
        user = User(
            email=req.email,
            name=odoo["name"],
            odoo_user_id=uid_str,
            odoo_instance_url=base_url,
            odoo_db=req.db,
            odoo_session_id=odoo["session_id"],
            is_verified=True,
        )
        db.add(user)
    else:
        user.odoo_session_id = odoo["session_id"]
        user.odoo_db = req.db
        user.name = odoo["name"]

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id})
    return {"access_token": token, "user": _user_dict(user)}


def _user_dict(user: User) -> dict:
    return {
        "id":      user.id,
        "email":   user.email,
        "name":    user.name,
        "company": user.company,
        "has_erp": bool(user.odoo_session_id),
        "erp_url": user.odoo_instance_url,
        "erp_db":  user.odoo_db,
    }
