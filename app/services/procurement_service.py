import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.database.models import (
    GroupRound,
    Pledge,
    Bid,
    Supplier,
    AuditLog,
)
from app.core.logging import logger


class ProcurementService:
    @classmethod
    def draft_group_request(
        cls,
        db: Session,
        business_id: str,
        item_name: str,
        target_quantity: int,
        target_cents: int,
        duration_days: int = 7,
        actor: str = "system"
    ) -> GroupRound:
        closes_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
        round_obj = GroupRound(
            initiator_business_id=business_id,
            item_name=item_name,
            target_quantity=target_quantity,
            current_quantity=0,
            target_cents=target_cents,
            current_cents=0,
            status="drafting",
            closes_at=closes_at
        )
        db.add(round_obj)
        db.flush()

        audit = AuditLog(
            business_id=business_id,
            actor=actor,
            resource="group_rounds",
            purpose=f"Drafted group bulk buying request for {target_quantity}x {item_name} (Target: R{target_cents/100:.2f})"
        )
        db.add(audit)
        db.commit()
        db.refresh(round_obj)
        return round_obj

    @classmethod
    def submit_group_request(
        cls,
        db: Session,
        business_id: str,
        round_id: str,
        actor: str = "system"
    ) -> GroupRound:
        round_obj = db.query(GroupRound).filter(
            GroupRound.id == round_id,
            GroupRound.initiator_business_id == business_id
        ).first()
        if not round_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group round not found")

        if round_obj.status != "drafting":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Round in status '{round_obj.status}' cannot be submitted"
            )

        round_obj.status = "open"
        audit = AuditLog(
            business_id=business_id,
            actor=actor,
            resource="group_rounds",
            purpose=f"Published group purchasing round #{round_obj.id} to open network"
        )
        db.add(audit)
        db.commit()
        db.refresh(round_obj)
        return round_obj

    @classmethod
    def add_pledge(
        cls,
        db: Session,
        business_id: str,
        round_id: str,
        quantity: int,
        amount_cents: int,
        actor: str = "system"
    ) -> Pledge:
        round_query = db.query(GroupRound).filter(GroupRound.id == round_id)
        if db.bind and db.bind.dialect.name != "sqlite":
            round_query = round_query.with_for_update()
        round_obj = round_query.first()
        closes_at = round_obj.closes_at if round_obj else None
        if closes_at is not None and closes_at.tzinfo is None:
            closes_at = closes_at.replace(tzinfo=timezone.utc)
        if (
            not round_obj
            or round_obj.status != "open"
            or (closes_at and closes_at <= datetime.now(timezone.utc))
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group round is not currently open for pledges")
        if quantity <= 0 or amount_cents <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pledge quantity and amount must be positive"
            )
        if round_obj.current_quantity + quantity > round_obj.target_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pledge would exceed the round's target quantity"
            )
        if round_obj.current_cents + amount_cents > round_obj.target_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pledge would exceed the round's target amount"
            )

        pledge = Pledge(
            round_id=round_id,
            business_id=business_id,
            quantity=quantity,
            amount_cents=amount_cents,
            payment_status="pledged"
        )
        db.add(pledge)

        # Update round progress
        round_obj.current_quantity += quantity
        round_obj.current_cents += amount_cents

        audit = AuditLog(
            business_id=business_id,
            actor=actor,
            resource="pledges",
            purpose=f"Pledged {quantity} items (R{amount_cents/100:.2f}) to round #{round_id}"
        )
        db.add(audit)
        db.commit()
        db.refresh(pledge)
        return pledge

    @classmethod
    def get_bid_status(cls, db: Session, round_id: str) -> Dict[str, Any]:
        round_obj = db.query(GroupRound).filter(GroupRound.id == round_id).first()
        if not round_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group round not found")

        bids = db.query(Bid).join(Supplier).filter(
            Bid.round_id == round_id,
            Supplier.is_verified.is_(True)
        ).all()
        return {
            "round_id": round_obj.id,
            "item_name": round_obj.item_name,
            "target_quantity": round_obj.target_quantity,
            "current_quantity": round_obj.current_quantity,
            "round_status": round_obj.status,
            "bids_count": len(bids),
            "bids": [
                {
                    "bid_id": b.id,
                    "supplier_name": b.supplier.name if b.supplier else "Unknown",
                    "unit_price_zar": round(b.unit_price_cents / 100.0, 2),
                    "status": b.status,
                    "delivery_terms": b.delivery_terms
                }
                for b in bids
            ]
        }

    @classmethod
    def compare_bids(cls, db: Session, round_id: str) -> Dict[str, Any]:
        status_info = cls.get_bid_status(db, round_id)
        bids = status_info["bids"]
        if not bids:
            return {"round_id": round_id, "recommendation": "No supplier bids submitted yet."}

        # Sort by unit price ascending
        sorted_bids = sorted(bids, key=lambda x: x["unit_price_zar"])
        best_bid = sorted_bids[0]
        return {
            "round_id": round_id,
            "best_bid": best_bid,
            "all_bids_ranked": sorted_bids,
            "recommendation": f"Best quotation from {best_bid['supplier_name']} at R{best_bid['unit_price_zar']:.2f}/unit."
        }
