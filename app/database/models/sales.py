from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.database.models.core import generate_uuid, utc_now


class Sale(Base):
    __tablename__ = "sales"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    total = Column(Integer, nullable=False)  # in integer cents
    payment_type = Column(String(32), default="cash", nullable=False)  # cash, card, spaza_credit, crypto
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sales_biz_created", "business_id", "created_at"),
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sale_id = Column(String(36), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    qty = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)  # in integer cents

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(64), nullable=False)  # transport, electricity, municipal, stock, rent, airtime
    amount = Column(Integer, nullable=False)  # in integer cents
    receipt_ref = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("idx_expenses_biz_created", "business_id", "created_at"),
    )
