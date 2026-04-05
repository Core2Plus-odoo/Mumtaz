from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ZAKI CFO AI"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://zaki:zaki@db:5432/zaki"

    # JWT
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # AI
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None  # for Whisper voice

    # Mumtaz ERP integration
    MUMTAZ_API_BASE: str = "https://app.mumtaz.digital"

    # Odoo OAuth SSO
    ODOO_CLIENT_ID: Optional[str] = None
    ODOO_CLIENT_SECRET: Optional[str] = None
    ODOO_BASE_URL: str = "https://app.mumtaz.digital"

    # CORS
    FRONTEND_URL: str = "https://zaki.mumtaz.digital"

    class Config:
        env_file = ".env"


settings = Settings()
