from typing import Dict, Any
from sqlalchemy.orm import Session
from app.services.procurement_service import ProcurementService


class PoolMCPServer:
    """
    Model Context Protocol (MCP) tool provider for Collaborative Group Purchasing.
    Preserves distinction between off-chain coordination and on-chain Avalanche Fuji bulk pools.
    """

    @classmethod
    def draft_group_request(
        cls,
        db: Session,
        business_id: str,
        item_name: str,
        target_quantity: int,
        target_cents: int,
        actor: str = "agent:procurement"
    ) -> Dict[str, Any]:
        round_obj = ProcurementService.draft_group_request(
            db=db,
            business_id=business_id,
            item_name=item_name,
            target_quantity=target_quantity,
            target_cents=target_cents,
            actor=actor
        )
        return {
            "round_id": round_obj.id,
            "item_name": round_obj.item_name,
            "target_quantity": round_obj.target_quantity,
            "status": round_obj.status
        }

    @classmethod
    def get_bid_status(cls, db: Session, round_id: str) -> Dict[str, Any]:
        return ProcurementService.get_bid_status(db, round_id)

    @classmethod
    def compare_bids(cls, db: Session, round_id: str) -> Dict[str, Any]:
        return ProcurementService.compare_bids(db, round_id)

    @classmethod
    def submit_group_request(
        cls,
        db: Session,
        business_id: str,
        round_id: str,
        actor: str = "agent:procurement"
    ) -> Dict[str, Any]:
        round_obj = ProcurementService.submit_group_request(
            db=db,
            business_id=business_id,
            round_id=round_id,
            actor=actor
        )
        return {"round_id": round_obj.id, "status": round_obj.status}
