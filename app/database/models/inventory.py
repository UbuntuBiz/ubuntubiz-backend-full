from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.core import generate_uuid, utc_now


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    unit = Column(String(32), default="item", nullable=False)  # item, kg, litre, loaf, pack
    cost_price = Column(Integer, nullable=True)  # in integer cents (e.g. 1500 = R15.00)
    sell_price = Column(Integer, nullable=False)  # in integer cents
    reorder_point = Column(Integer, default=5, nullable=False)
    expiry_tracked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    aliases = relationship("ProductAlias", back_populates="product", cascade="all, delete-orphan")
    stock_level = relationship("StockLevel", back_populates="product", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_products_biz_name", "business_id", "name"),
    )


class ProductAlias(Base):
    __tablename__ = "product_aliases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(255), nullable=False, index=True)

    product = relationship("Product", back_populates="aliases")

    __table_args__ = (
        Index("idx_alias_biz_lookup", "business_id", "alias"),
    )


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(32), nullable=False)  # sale, purchase, adjustment, delivery, reversal
    qty_delta = Column(Integer, nullable=False)  # positive for stock-in, negative for stock-out
    unit_cost = Column(Integer, nullable=True)  # cents
    unit_price = Column(Integer, nullable=True)  # cents
    actor = Column(String(128), nullable=False)  # user id, agent name, system
    reason = Column(String(255), nullable=False)
    trace_id = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    reverses_event_id = Column(String(36), ForeignKey("inventory_events.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_inventory_event_biz_idempotency"),
        Index("idx_inv_event_biz_prod", "business_id", "product_id", "created_at"),
    )


class StockLevel(Base):
    __tablename__ = "stock_levels"

    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    qty_on_hand = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    product = relationship("Product", back_populates="stock_level")
