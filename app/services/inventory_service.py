import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.database.models import (
    Product,
    StockLevel,
    InventoryEvent,
    AuditLog,
)
from app.core.logging import logger


class InventoryService:
    @staticmethod
    def get_or_create_stock_level(db: Session, business_id: str, product_id: str) -> StockLevel:
        stock = db.query(StockLevel).filter(
            StockLevel.business_id == business_id,
            StockLevel.product_id == product_id
        ).with_for_update().first() if db.bind and db.bind.dialect.name != "sqlite" else db.query(StockLevel).filter(
            StockLevel.business_id == business_id,
            StockLevel.product_id == product_id
        ).first()

        if not stock:
            stock = StockLevel(
                business_id=business_id,
                product_id=product_id,
                qty_on_hand=0,
                updated_at=datetime.now(timezone.utc)
            )
            db.add(stock)
            db.flush()
        return stock

    @classmethod
    def apply_inventory_event(
        cls,
        db: Session,
        business_id: str,
        product_id: str,
        event_type: str,
        qty_delta: int,
        reason: str,
        idempotency_key: str,
        actor: str = "system",
        trace_id: Optional[str] = None,
        unit_cost: Optional[int] = None,
        unit_price: Optional[int] = None,
        reverses_event_id: Optional[str] = None,
        allow_negative_stock: bool = False
    ) -> InventoryEvent:
        """
        Core atomic event-based ledger write.
        Updates stock_level and appends to inventory_events within the current transaction.
        """
        # Idempotency check
        existing_event = db.query(InventoryEvent).filter(
            InventoryEvent.business_id == business_id,
            InventoryEvent.idempotency_key == idempotency_key
        ).first()
        if existing_event:
            return existing_event

        product = db.query(Product).filter(
            Product.id == product_id,
            Product.business_id == business_id
        ).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product '{product_id}' not found for business"
            )

        stock = cls.get_or_create_stock_level(db, business_id, product_id)

        # Validate negative stock
        new_qty = stock.qty_on_hand + qty_delta
        if new_qty < 0 and not allow_negative_stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{product.name}'. Current: {stock.qty_on_hand}, Requested delta: {qty_delta}"
            )

        resolved_trace_id = trace_id or str(uuid.uuid4())

        # Create immutable event record
        event = InventoryEvent(
            business_id=business_id,
            product_id=product_id,
            type=event_type,
            qty_delta=qty_delta,
            unit_cost=unit_cost if unit_cost is not None else product.cost_price,
            unit_price=unit_price if unit_price is not None else product.sell_price,
            actor=actor,
            reason=reason,
            trace_id=resolved_trace_id,
            idempotency_key=idempotency_key,
            reverses_event_id=reverses_event_id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(event)

        # Update stock level atomically
        stock.qty_on_hand = new_qty
        stock.updated_at = datetime.now(timezone.utc)

        # Log audit trail
        audit = AuditLog(
            business_id=business_id,
            actor=actor,
            resource="inventory_events",
            purpose=f"{event_type.capitalize()} on {product.name} (delta: {qty_delta}, new_stock: {new_qty}) - Reason: {reason}"
        )
        db.add(audit)

        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency conflict: transaction already processed"
            )

        return event

    @classmethod
    def adjust_stock(
        cls,
        db: Session,
        business_id: str,
        product_id: str,
        qty_delta: int,
        reason: str,
        idempotency_key: str,
        actor: str = "system",
        trace_id: Optional[str] = None
    ) -> InventoryEvent:
        return cls.apply_inventory_event(
            db=db,
            business_id=business_id,
            product_id=product_id,
            event_type="adjustment",
            qty_delta=qty_delta,
            reason=reason,
            idempotency_key=idempotency_key,
            actor=actor,
            trace_id=trace_id
        )

    @classmethod
    def record_purchase(
        cls,
        db: Session,
        business_id: str,
        items: List[Dict[str, Any]],
        idempotency_key: str,
        actor: str = "system",
        trace_id: Optional[str] = None
    ) -> List[InventoryEvent]:
        events = []
        for idx, item in enumerate(items):
            item_key = f"{idempotency_key}_item_{idx}"
            ev = cls.apply_inventory_event(
                db=db,
                business_id=business_id,
                product_id=item["product_id"],
                event_type="purchase",
                qty_delta=item["qty"],
                reason=item.get("reason", "Purchased stock from supplier"),
                idempotency_key=item_key,
                actor=actor,
                trace_id=trace_id,
                unit_cost=item.get("unit_cost")
            )
            events.append(ev)
        return events

    @classmethod
    def receive_delivery(
        cls,
        db: Session,
        business_id: str,
        items: List[Dict[str, Any]],
        idempotency_key: str,
        actor: str = "system",
        trace_id: Optional[str] = None
    ) -> List[InventoryEvent]:
        events = []
        for idx, item in enumerate(items):
            item_key = f"{idempotency_key}_delivery_{idx}"
            ev = cls.apply_inventory_event(
                db=db,
                business_id=business_id,
                product_id=item["product_id"],
                event_type="delivery",
                qty_delta=item["qty"],
                reason=item.get("reason", "Received delivery from group round"),
                idempotency_key=item_key,
                actor=actor,
                trace_id=trace_id,
                unit_cost=item.get("unit_cost")
            )
            events.append(ev)
        return events

    @classmethod
    def undo_event(
        cls,
        db: Session,
        business_id: str,
        event_id: str,
        actor: str = "system",
        reason: str = "Reversing incorrect inventory transaction"
    ) -> InventoryEvent:
        """
        Reverses an existing inventory event by appending an inverse event.
        Never deletes or modifies original event history.
        """
        original = db.query(InventoryEvent).filter(
            InventoryEvent.id == event_id,
            InventoryEvent.business_id == business_id
        ).first()
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory event '{event_id}' not found"
            )

        # Check if already reversed
        already_reversed = db.query(InventoryEvent).filter(
            InventoryEvent.reverses_event_id == original.id,
            InventoryEvent.business_id == business_id
        ).first()
        if already_reversed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This inventory event has already been reversed"
            )

        reversal_key = f"reversal_{original.id}"
        reversal_event = cls.apply_inventory_event(
            db=db,
            business_id=business_id,
            product_id=original.product_id,
            event_type="reversal",
            qty_delta=-original.qty_delta,  # Opposite delta
            reason=f"Undo event {original.id}: {reason}",
            idempotency_key=reversal_key,
            actor=actor,
            trace_id=f"reversal-{original.trace_id}",
            unit_cost=original.unit_cost,
            unit_price=original.unit_price,
            reverses_event_id=original.id,
            allow_negative_stock=False
        )
        return reversal_event

    @staticmethod
    def get_stock(db: Session, business_id: str, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = db.query(Product, StockLevel).outerjoin(
            StockLevel,
            (StockLevel.product_id == Product.id) & (StockLevel.business_id == Product.business_id)
        ).filter(Product.business_id == business_id)

        if product_id:
            query = query.filter(Product.id == product_id)

        results = query.all()
        stock_list = []
        for prod, stock in results:
            qty = stock.qty_on_hand if stock else 0
            stock_list.append({
                "product_id": prod.id,
                "product_name": prod.name,
                "qty_on_hand": qty,
                "reorder_point": prod.reorder_point,
                "is_low_stock": qty <= prod.reorder_point,
                "unit": prod.unit,
                "sell_price": prod.sell_price,
                "updated_at": stock.updated_at if stock else prod.created_at
            })
        return stock_list

    @staticmethod
    def list_low_stock(db: Session, business_id: str) -> List[Dict[str, Any]]:
        all_stock = InventoryService.get_stock(db, business_id)
        return [item for item in all_stock if item["is_low_stock"]]
