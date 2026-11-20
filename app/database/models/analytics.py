from sqlalchemy import Column, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Index
from app.database.connection import Base
from app.database.models.core import generate_uuid, utc_now


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    metric = Column(String(64), nullable=False)  # daily_sales, gross_profit, days_of_stock, reorder_point, dead_stock, cash_variance
    value = Column(Float, nullable=False)
    is_estimate = Column(Boolean, default=False, nullable=False)
    computed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_metrics_lookup", "business_id", "date", "metric"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    business_id = Column(String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(64), nullable=False)  # low_stock_risk, sales_drop, cash_variance
    product_id = Column(String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    message = Column(String(500), nullable=False)
    status = Column(String(32), default="active", nullable=False)  # active, dismissed, resolved
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("idx_alerts_biz_status", "business_id", "status"),
    )
