from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, Index, JSON, UniqueConstraint
from app.database.connection import Base
from app.database.models.core import generate_uuid, utc_now


class BlockchainTransaction(Base):
    __tablename__ = "blockchain_transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    transaction_hash = Column(String(66), nullable=False, unique=True, index=True)
    block_number = Column(BigInteger, nullable=True, index=True)
    transaction_status = Column(String(32), default="pending", nullable=False)  # pending, confirmed, failed
    contract_address = Column(String(42), nullable=False, index=True)
    related_business_id = Column(String(36), ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    function_name = Column(String(64), nullable=True)  # recordSale, createBulkPool, joinBulkPool, createOrder, approveOrder
    value_wei = Column(String(78), default="0", nullable=False)  # Big numeric stored as string to avoid precision loss
    gas_used = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class BlockchainEvent(Base):
    __tablename__ = "blockchain_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_name = Column(String(64), nullable=False, index=True)  # SaleRecorded, PoolCreated, PoolJoined, OrderCreated, OrderApproved
    event_id = Column(String(64), nullable=False)  # onchain saleId, poolId, orderId
    transaction_hash = Column(String(66), nullable=False, index=True)
    block_number = Column(BigInteger, nullable=False, index=True)
    contract_address = Column(String(42), nullable=False, index=True)
    payload_json = Column(JSON, nullable=False)
    related_business_id = Column(String(36), ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("contract_address", "event_name", "event_id", name="uq_contract_event_id"),
        Index("idx_bc_event_lookup", "event_name", "event_id"),
    )


class BlockchainSyncCheckpoint(Base):
    __tablename__ = "blockchain_sync_checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_address = Column(String(42), nullable=False, unique=True, index=True)
    last_synced_block = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
