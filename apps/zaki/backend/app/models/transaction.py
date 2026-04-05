from sqlalchemy import Column, String, Float, Date, DateTime, Text, Enum, ForeignKey
from sqlalchemy.sql import func
import uuid
import enum
from app.db.database import Base


class TxType(str, enum.Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"


class TxSource(str, enum.Enum):
    manual = "manual"
    upload = "upload"
    erp_sync = "erp_sync"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(Enum(TxType), nullable=False)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    reference = Column(String, nullable=True)
    currency = Column(String, default="USD")

    source = Column(Enum(TxSource), default=TxSource.manual)
    erp_id = Column(String, nullable=True)  # original ID from Mumtaz ERP

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AISession(Base):
    __tablename__ = "ai_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("ai_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
