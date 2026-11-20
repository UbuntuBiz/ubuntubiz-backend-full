from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService
from app.core.tenant import get_current_business_id
from app.core.logging import logger


class InventoryMCPServer:
    """
    Model Context Protocol (MCP) tool provider for Spaza Inventory Operations.
    Agents NEVER access database directly; all calls invoke the service layer.
    """

    @classmethod
    def get_stock(cls, db: Session, business_id: str, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return InventoryService.get_stock(db, business_id, product_id=product_id)

    @classmethod
    def list_low_stock(cls, db: Session, business_id: str) -> List[Dict[str, Any]]:
        return InventoryService.list_low_stock(db, business_id)

    @classmethod
    def record_sale(
        cls,
        db: Session,
        business_id: str,
        items: List[Dict[str, Any]],
        payment_type: str,
        idempotency_key: str,
        actor: str = "agent:capture",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sale = SalesService.record_sale(
            db=db,
            business_id=business_id,
            items=items,
            payment_type=payment_type,
            idempotency_key=idempotency_key,
            actor=actor,
            trace_id=trace_id
        )
        return {
            "sale_id": sale.id,
            "total_cents": sale.total,
            "total_zar": round(sale.total / 100.0, 2),
            "payment_type": sale.payment_type,
            "items_count": len(sale.items)
        }

    @classmethod
    def record_purchase(
        cls,
        db: Session,
        business_id: str,
        items: List[Dict[str, Any]],
        idempotency_key: str,
        actor: str = "agent:procurement",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        events = InventoryService.record_purchase(
            db=db,
            business_id=business_id,
            items=items,
            idempotency_key=idempotency_key,
            actor=actor,
            trace_id=trace_id
        )
        return {"events_count": len(events), "status": "purchased"}

    @classmethod
    def receive_delivery(
        cls,
        db: Session,
        business_id: str,
        items: List[Dict[str, Any]],
        idempotency_key: str,
        actor: str = "agent:verification",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        events = InventoryService.receive_delivery(
            db=db,
            business_id=business_id,
            items=items,
            idempotency_key=idempotency_key,
            actor=actor,
            trace_id=trace_id
        )
        return {"delivered_items": len(events), "status": "delivery_received"}

    @classmethod
    def adjust_stock(
        cls,
        db: Session,
        business_id: str,
        product_id: str,
        qty_delta: int,
        reason: str,
        idempotency_key: str,
        actor: str = "agent:inventory",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        ev = InventoryService.adjust_stock(
            db=db,
            business_id=business_id,
            product_id=product_id,
            qty_delta=qty_delta,
            reason=reason,
            idempotency_key=idempotency_key,
            actor=actor,
            trace_id=trace_id
        )
        return {"event_id": ev.id, "product_id": ev.product_id, "qty_delta": ev.qty_delta}

    @classmethod
    def undo_event(
        cls,
        db: Session,
        business_id: str,
        event_id: str,
        actor: str = "agent:policy"
    ) -> Dict[str, Any]:
        reversal = InventoryService.undo_event(
            db=db,
            business_id=business_id,
            event_id=event_id,
            actor=actor
        )
        return {"reversal_id": reversal.id, "reverses_event_id": reversal.reverses_event_id}
