from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
import uuid
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=True)  # null for SSO-only users
    company = Column(String, nullable=True)

    # Odoo connection
    odoo_user_id = Column(String, nullable=True)
    odoo_instance_url = Column(String, nullable=True)
    odoo_db = Column(String, nullable=True)
    odoo_session_id = Column(Text, nullable=True)
    odoo_access_token = Column(Text, nullable=True)
    erp_api_key = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
