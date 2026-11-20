from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import InventoryEvent, User
from app.schemas.inventory import (
    InventoryEventCreate,
    InventoryEventResponse,
    StockLevelResponse,
)
from app.services.inventory_service import InventoryService
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/inventory", tags=["Inventory & Event Ledger"])


@router.get("", response_model=List[StockLevelResponse])
def get_current_inventory(
    product_id: Optional[str] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Get real-time stock levels for all products or a specific product.
    """
    return InventoryService.get_stock(db, current_user.business_id, product_id=product_id)


@router.post("/events", response_model=InventoryEventResponse, status_code=status.HTTP_201_CREATED)
def record_inventory_event(
    req: InventoryEventCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Append an event to the insert-only inventory ledger (adjustment, damage, delivery, purchase).
    Updates stock levels atomically.
    """
    event = InventoryService.apply_inventory_event(
        db=db,
        business_id=current_user.business_id,
        product_id=req.product_id,
        event_type=req.type,
        qty_delta=req.qty_delta,
        reason=req.reason,
        idempotency_key=req.idempotency_key,
        actor=current_user.id,
        unit_cost=req.unit_cost,
        unit_price=req.unit_price
    )
    db.commit()
    db.refresh(event)
    return event


@router.get("/events", response_model=List[InventoryEventResponse])
def get_inventory_events(
    product_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve audit trail of immutable inventory ledger events.
    """
    query = db.query(InventoryEvent).filter(InventoryEvent.business_id == current_user.business_id)
    if product_id:
        query = query.filter(InventoryEvent.product_id == product_id)
    
    events = query.order_by(InventoryEvent.created_at.desc()).offset(offset).limit(limit).all()
    return events


@router.post("/undo/{event_id}", response_model=InventoryEventResponse)
def undo_inventory_event(
    event_id: str,
    reason: Optional[str] = "Owner requested transaction reversal",
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Undo a previous inventory event by creating a compensating reversal event.
    Preserves audit history and prevents overwriting past data.
    """
    reversal = InventoryService.undo_event(
        db=db,
        business_id=current_user.business_id,
        event_id=event_id,
        actor=current_user.id,
        reason=reason
    )
    db.commit()
    db.refresh(reversal)
    return reversal
