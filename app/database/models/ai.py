from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.core import generate_uuid, utc_now


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    parent_id = Column(String(36), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    intent = Column(String(128), nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, in_progress, awaiting_approval, completed, failed
    input_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    cost = Column(Float, default=0.0, nullable=False)  # USD Gemini API estimated cost
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    tool_calls = relationship("AgentToolCall", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="task", cascade="all, delete-orphan")


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    agent = Column(String(64), nullable=False)  # capture, inventory, analytics, procurement, policy, verification
    tool = Column(String(64), nullable=False)  # e.g. record_sale, get_stock
    args_json = Column(JSON, nullable=True)
    status = Column(String(32), default="executed", nullable=False)  # executed, rejected_policy, failed
    latency = Column(Float, default=0.0, nullable=False)  # seconds
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    task = relationship("AgentTask", back_populates="tool_calls")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # e.g., "confirm_sale", "submit_pool_pledge", "stock_adjustment"
    summary = Column(Text, nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, approved, rejected
    decided_via = Column(String(32), nullable=True)  # web, whatsapp, pin_confirmation
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    task = relationship("AgentTask", back_populates="approvals")

    __table_args__ = (
        Index("idx_approvals_biz_status", "business_id", "status"),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scope = Column(String(32), default="global", nullable=False)  # global, business_private
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)
    text = Column(Text, nullable=False)
    source = Column(String(255), nullable=False)  # doc reference, product catalog, POPIA act
    source_date = Column(String(32), nullable=False)  # e.g., "2026-01-15"
    embedding = Column(JSON, nullable=True)  # vector embedding float list or pgvector
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(32), default="whatsapp", nullable=False)  # whatsapp, web_chat, sms
    external_msg_id = Column(String(128), nullable=False, index=True)
    direction = Column(String(16), nullable=False)  # inbound, outbound
    type = Column(String(32), default="text", nullable=False)  # text, voice_note, image_receipt, interactive
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("idx_messages_idempotency", "channel", "external_msg_id", unique=True),
    )
