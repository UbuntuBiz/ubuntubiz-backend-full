from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.core import generate_uuid, utc_now


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    contact_phone = Column(String(32), nullable=False, unique=True, index=True)
    area = Column(String(255), nullable=False)
    catalog_summary = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    bids = relationship("Bid", back_populates="supplier")
    credentials = relationship("Credential", back_populates="supplier", cascade="all, delete-orphan")


class GroupRound(Base):
    __tablename__ = "group_rounds"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    initiator_business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(String(255), nullable=False)
    target_quantity = Column(Integer, nullable=False)
    current_quantity = Column(Integer, default=0, nullable=False)
    target_cents = Column(Integer, nullable=False)
    current_cents = Column(Integer, default=0, nullable=False)
    onchain_pool_id = Column(String(64), nullable=True, index=True)  # Links to Avalanche Fuji BulkPool id if created
    status = Column(String(32), default="open", nullable=False)  # drafting, open, locked, bidding, settled, cancelled
    closes_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    pledges = relationship("Pledge", back_populates="round", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="round", cascade="all, delete-orphan")
    deliveries = relationship("Delivery", back_populates="round", cascade="all, delete-orphan")


class Pledge(Base):
    __tablename__ = "pledges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    round_id = Column(String(36), ForeignKey("group_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    payment_status = Column(String(32), default="pledged", nullable=False)  # pledged, funded_onchain, settled
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    round = relationship("GroupRound", back_populates="pledges")


class Bid(Base):
    __tablename__ = "bids"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    round_id = Column(String(36), ForeignKey("group_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_price_cents = Column(Integer, nullable=False)
    delivery_terms = Column(Text, nullable=True)
    status = Column(String(32), default="submitted", nullable=False)  # submitted, accepted, rejected
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    round = relationship("GroupRound", back_populates="bids")
    supplier = relationship("Supplier", back_populates="bids")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    round_id = Column(String(36), ForeignKey("group_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False)  # pending, in_transit, delivered, confirmed
    dual_signed = Column(Boolean, default=False, nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    round = relationship("GroupRound", back_populates="deliveries")


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_type = Column(String(64), nullable=False)  # e.g., "tax_clearance", "bbbee_certificate", "food_safety"
    issuer = Column(String(255), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    supplier = relationship("Supplier", back_populates="credentials")
