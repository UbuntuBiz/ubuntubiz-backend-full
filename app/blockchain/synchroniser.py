from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database.models import (
    BlockchainSyncCheckpoint,
    BlockchainEvent,
)
from app.blockchain.provider import provider
from app.core.logging import logger


class BlockchainSynchroniser:
    """
    Synchronises past and new events from UbuntuBiz contract on Avalanche Fuji to PostgreSQL.
    Tracks checkpoints to avoid missing or re-scanning events.
    """

    @classmethod
    def get_or_create_checkpoint(cls, db: Session) -> BlockchainSyncCheckpoint:
        contract_addr = provider.contract_address
        checkpoint = db.query(BlockchainSyncCheckpoint).filter(
            BlockchainSyncCheckpoint.contract_address == contract_addr
        ).first()

        if not checkpoint:
            checkpoint = BlockchainSyncCheckpoint(
                contract_address=contract_addr,
                last_synced_block=0,
                updated_at=datetime.now(timezone.utc)
            )
            db.add(checkpoint)
            db.commit()
            db.refresh(checkpoint)
        return checkpoint

    @classmethod
    def sync_events(
        cls,
        db: Session,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> Dict[str, Any]:
        provider.verify_network()
        contract = provider.get_contract()
        w3 = provider.w3

        checkpoint = cls.get_or_create_checkpoint(db)

        current_head = to_block or w3.eth.block_number
        start_block = from_block if from_block is not None else (checkpoint.last_synced_block + 1 if checkpoint.last_synced_block > 0 else current_head - 100)
        start_block = max(0, start_block)

        if start_block > current_head:
            return {
                "synced_from": start_block,
                "synced_to": current_head,
                "events_found": 0,
                "checkpoint": checkpoint.last_synced_block
            }

        logger.info(f"Syncing UbuntuBiz events from block {start_block} to {current_head}...")

        total_synced = 0
        events_to_scan = [
            ("SaleRecorded", contract.events.SaleRecorded),
            ("PoolCreated", contract.events.PoolCreated),
            ("PoolJoined", contract.events.PoolJoined),
            ("OrderCreated", contract.events.OrderCreated),
            ("OrderApproved", contract.events.OrderApproved),
        ]

        for name, event_obj in events_to_scan:
            try:
                logs = event_obj.get_logs(from_block=start_block, to_block=current_head)
                for entry in logs:
                    raw_args = dict(entry["args"])
                    serializable_args = {
                        k: str(v) if isinstance(v, (int, bytes)) else v
                        for k, v in raw_args.items()
                    }
                    event_id = str(
                        raw_args.get("saleId") or
                        raw_args.get("poolId") or
                        raw_args.get("orderId") or
                        f"{entry['transactionHash'].hex()}_{entry['logIndex']}"
                    )

                    # Deduplication check
                    existing = db.query(BlockchainEvent).filter(
                        BlockchainEvent.contract_address == provider.contract_address,
                        BlockchainEvent.event_name == name,
                        BlockchainEvent.event_id == event_id
                    ).first()

                    if not existing:
                        ev = BlockchainEvent(
                            event_name=name,
                            event_id=event_id,
                            transaction_hash=entry["transactionHash"].hex(),
                            block_number=entry["blockNumber"],
                            contract_address=provider.contract_address,
                            payload_json=serializable_args
                        )
                        db.add(ev)
                        total_synced += 1
            except Exception as e:
                logger.warning(
                    f"Error fetching {name} logs ({type(e).__name__})"
                )

        checkpoint.last_synced_block = current_head
        checkpoint.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "synced_from": start_block,
            "synced_to": current_head,
            "events_found": total_synced,
            "checkpoint": checkpoint.last_synced_block
        }
