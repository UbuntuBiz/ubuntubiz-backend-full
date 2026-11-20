from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import Sale, SaleItem, User
from app.schemas.sales import SaleCreate, SaleResponse, SaleItemResponse, SalesSummaryResponse
from app.services.sales_service import SalesService
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/sales", tags=["Sales Operations"])


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def record_sale(
    req: SaleCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Record an informal business sale:
    - Atomically reduces inventory
    - Records financial transaction in integer cents
    - Idempotency-guaranteed
    """
    items_payload = [
        {"product_id": it.product_id, "qty": it.qty, "unit_price": it.unit_price}
        for it in req.items
    ]

    sale = SalesService.record_sale(
        db=db,
        business_id=current_user.business_id,
        items=items_payload,
        payment_type=req.payment_type,
        idempotency_key=req.idempotency_key,
        actor=current_user.id
    )

    items_resp = [
        SaleItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name if item.product else None,
            qty=item.qty,
            unit_price=item.unit_price
        )
        for item in sale.items
    ]

    return SaleResponse(
        id=sale.id,
        business_id=sale.business_id,
        total=sale.total,
        total_zar=round(sale.total / 100.0, 2),
        payment_type=sale.payment_type,
        created_at=sale.created_at,
        items=items_resp
    )


@router.get("", response_model=List[SaleResponse])
def list_sales(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List historical sales for the authenticated shop.
    """
    sales = db.query(Sale).filter(
        Sale.business_id == current_user.business_id
    ).order_by(Sale.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for s in sales:
        items_resp = [
            SaleItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else None,
                qty=item.qty,
                unit_price=item.unit_price
            )
            for item in s.items
        ]
        results.append(SaleResponse(
            id=s.id,
            business_id=s.business_id,
            total=s.total,
            total_zar=round(s.total / 100.0, 2),
            payment_type=s.payment_type,
            created_at=s.created_at,
            items=items_resp
        ))
    return results


@router.get("/summary", response_model=SalesSummaryResponse)
def get_sales_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve aggregated sales summary, cash vs card breakdown, and net cash flow.
    """
    return SalesService.get_sales_summary(
        db=db,
        business_id=current_user.business_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(
    sale_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    sale = db.query(Sale).filter(
        Sale.id == sale_id,
        Sale.business_id == current_user.business_id
    ).first()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    items_resp = [
        SaleItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name if item.product else None,
            qty=item.qty,
            unit_price=item.unit_price
        )
        for item in sale.items
    ]

    return SaleResponse(
        id=sale.id,
        business_id=sale.business_id,
        total=sale.total,
        total_zar=round(sale.total / 100.0, 2),
        payment_type=sale.payment_type,
        created_at=sale.created_at,
        items=items_resp
    )
