from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import (
    GroupRound,
    Pledge,
    Bid,
    Supplier,
    User,
)
from app.schemas.pools import (
    GroupRoundCreate,
    GroupRoundResponse,
    PledgeCreate,
    PledgeResponse,
    BidResponse,
    SupplierCreate,
    SupplierResponse,
)
from app.services.procurement_service import ProcurementService
from app.api.deps import get_current_user_and_tenant
from app.core.permissions import Role

router = APIRouter(prefix="/pools", tags=["Group Purchasing & Bulk Buying"])


def format_round_response(r: GroupRound) -> GroupRoundResponse:
    pledge_resps = [
        PledgeResponse(
            id=p.id,
            round_id=p.round_id,
            business_id=p.business_id,
            quantity=p.quantity,
            amount_cents=p.amount_cents,
            amount_zar=round(p.amount_cents / 100.0, 2),
            payment_status=p.payment_status,
            created_at=p.created_at
        )
        for p in r.pledges
    ]
    bid_resps = [
        BidResponse(
            id=b.id,
            round_id=b.round_id,
            supplier_id=b.supplier_id,
            supplier_name=b.supplier.name if b.supplier else None,
            unit_price_cents=b.unit_price_cents,
            unit_price_zar=round(b.unit_price_cents / 100.0, 2),
            delivery_terms=b.delivery_terms,
            status=b.status,
            created_at=b.created_at
        )
        for b in r.bids
    ]
    progress = round((r.current_quantity / r.target_quantity * 100.0), 1) if r.target_quantity > 0 else 0.0

    return GroupRoundResponse(
        id=r.id,
        initiator_business_id=r.initiator_business_id,
        item_name=r.item_name,
        target_quantity=r.target_quantity,
        current_quantity=r.current_quantity,
        target_cents=r.target_cents,
        target_zar=round(r.target_cents / 100.0, 2),
        current_cents=r.current_cents,
        current_zar=round(r.current_cents / 100.0, 2),
        progress_percent=progress,
        onchain_pool_id=r.onchain_pool_id,
        status=r.status,
        closes_at=r.closes_at,
        created_at=r.created_at,
        pledges=pledge_resps,
        bids=bid_resps
    )


@router.post("", response_model=GroupRoundResponse, status_code=status.HTTP_201_CREATED)
def create_group_round(
    req: GroupRoundCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Initiate an off-chain collaborative bulk buying round.
    Preserves distinction between application records and Avalanche Fuji on-chain pools.
    """
    if current_user.role != Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a business owner may open a group purchasing round"
        )

    round_obj = ProcurementService.draft_group_request(
        db=db,
        business_id=current_user.business_id,
        item_name=req.item_name,
        target_quantity=req.target_quantity,
        target_cents=req.target_cents,
        duration_days=req.duration_days,
        actor=current_user.id
    )
    # Default newly drafted round to open
    round_obj.status = "open"
    db.commit()
    db.refresh(round_obj)
    return format_round_response(round_obj)


@router.get("", response_model=List[GroupRoundResponse])
def list_group_rounds(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List collaborative group buying rounds across the township network.
    """
    query = db.query(GroupRound)
    if status_filter:
        query = query.filter(GroupRound.status == status_filter)
    rounds = query.order_by(GroupRound.created_at.desc()).all()
    return [format_round_response(r) for r in rounds]


@router.get("/suppliers", response_model=List[SupplierResponse])
def list_suppliers(
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List verified suppliers available for group purchasing.
    """
    suppliers = db.query(Supplier).filter(Supplier.is_verified.is_(True)).all()
    return suppliers


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def register_supplier(
    req: SupplierCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    if current_user.role != Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a business owner may register a supplier"
        )

    supplier = Supplier(
        name=req.name,
        contact_phone=req.contact_phone,
        area=req.area,
        catalog_summary=req.catalog_summary,
        is_verified=False
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/{round_id}", response_model=GroupRoundResponse)
def get_group_round(
    round_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    round_obj = db.query(GroupRound).filter(GroupRound.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group round not found")
    return format_round_response(round_obj)


@router.post("/{round_id}/pledges", response_model=PledgeResponse, status_code=status.HTTP_201_CREATED)
def pledge_to_group_round(
    round_id: str,
    req: PledgeCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Pledge stock quantity and contribution to an open bulk buying round.
    """
    if current_user.role != Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a business owner may commit a pledge"
        )

    pledge = ProcurementService.add_pledge(
        db=db,
        business_id=current_user.business_id,
        round_id=round_id,
        quantity=req.quantity,
        amount_cents=req.amount_cents,
        actor=current_user.id
    )
    return PledgeResponse(
        id=pledge.id,
        round_id=pledge.round_id,
        business_id=pledge.business_id,
        quantity=pledge.quantity,
        amount_cents=pledge.amount_cents,
        amount_zar=round(pledge.amount_cents / 100.0, 2),
        payment_status=pledge.payment_status,
        created_at=pledge.created_at
    )


@router.get("/{round_id}/status")
def get_round_bid_status(
    round_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Get quotation bidding status and comparative recommendation for a group round.
    """
    return ProcurementService.compare_bids(db, round_id)
