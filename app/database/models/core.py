import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Business(Base):
    __tablename__ = "businesses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    area = Column(String(255), nullable=False)  # e.g., "Soweto - Orlando West", "Khayelitsha"
    owner_phone = Column(String(32), nullable=False, unique=True, index=True)
    language = Column(String(16), default="en", nullable=False)  # "en", "zu", "xh", "st"
    status = Column(String(32), default="active", nullable=False)  # "active", "suspended"
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    users = relationship("User", back_populates="business", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    phone = Column(String(32), nullable=False, unique=True, index=True)
    role = Column(String(32), default="owner", nullable=False)  # "owner", "manager", "cashier"
    pin_hash = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    business = relationship("Business", back_populates="users")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    actor = Column(String(128), nullable=False)  # User ID, Agent Name, or System
    resource = Column(String(128), nullable=False)  # e.g. "inventory_events", "sales", "approvals"
    purpose = Column(Text, nullable=False)  # Reason / trace description
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("idx_audit_biz_created", "business_id", "created_at"),
    )
