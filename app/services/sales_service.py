import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.database.models import (
    Sale,
    SaleItem,
    Product,
    Expense,
    AuditLog,
)
from app.services.inventory_service import InventoryService
from app.core.logging import logger


class SalesService:
    @classmethod
    def record_sale(
        cls,
        db: Session,
        business_id: str,
        items: List[Dict[str, Any]],
        payment_type: str,
        idempotency_key: str,
        actor: str = "system",
        trace_id: Optional[str] = None
    ) -> Sale:
        """
        Record a customer sale atomically:
        1. Validates all products.
        2. Calculates total in integer cents.
        3. Appends inventory sale events (decrementing stock) with negative stock validation.
        4. Saves Sale and SaleItem records.
        """
        resolved_trace_id = trace_id or str(uuid.uuid4())

        # Check idempotency on the primary sale level
        existing_sale = db.query(Sale).filter(
            Sale.business_id == business_id,
            Sale.idempotency_key == idempotency_key
        ).first()
        if existing_sale:
            return existing_sale

        total_cents = 0
        sale_items_to_create = []

        # Validate products and prices first
        for idx, item in enumerate(items):
            product_id = item["product_id"]
            qty = item["qty"]
            if qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sale quantity must be positive, got {qty}"
                )

            product = db.query(Product).filter(
                Product.id == product_id,
                Product.business_id == business_id
            ).first()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product '{product_id}' not found for business"
                )

            unit_price = item.get("unit_price")
            if unit_price is None:
                unit_price = product.sell_price

            line_total = unit_price * qty
            total_cents += line_total

            sale_items_to_create.append({
                "product_id": product.id,
                "qty": qty,
                "unit_cost": product.cost_price,
                "unit_price": unit_price,
                "product_name": product.name,
                "idx": idx
            })

        # Create Sale
        sale = Sale(
            id=str(uuid.uuid4()),
            business_id=business_id,
            total=total_cents,
            payment_type=payment_type,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc)
        )
        db.add(sale)

        # Deduct stock and record sale items
        for entry in sale_items_to_create:
            item_idempotency_key = f"{idempotency_key}_sale_{entry['idx']}_{entry['product_id']}"
            try:
                InventoryService.apply_inventory_event(
                    db=db,
                    business_id=business_id,
                    product_id=entry["product_id"],
                    event_type="sale",
                    qty_delta=-entry["qty"],  # Decrease stock
                    reason=f"Sale #{sale.id} ({entry['qty']} x {entry['product_name']})",
                    idempotency_key=item_idempotency_key,
                    actor=actor,
                    trace_id=resolved_trace_id,
                    unit_price=entry["unit_price"]
                )
            except HTTPException:
                db.rollback()
                existing_sale = db.query(Sale).filter(
                    Sale.business_id == business_id,
                    Sale.idempotency_key == idempotency_key
                ).first()
                if existing_sale:
                    return existing_sale
                raise

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=entry["product_id"],
                qty=entry["qty"],
                unit_cost=entry["unit_cost"],
                unit_price=entry["unit_price"]
            )
            db.add(sale_item)

        # Audit
        audit = AuditLog(
            business_id=business_id,
            actor=actor,
            resource="sales",
            purpose=f"Recorded sale #{sale.id} total R{total_cents / 100:.2f} ({payment_type})"
        )
        db.add(audit)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_sale = db.query(Sale).filter(
                Sale.business_id == business_id,
                Sale.idempotency_key == idempotency_key
            ).first()
            if existing_sale:
                return existing_sale
            raise
        db.refresh(sale)
        return sale

    @classmethod
    def record_expense(
        cls,
        db: Session,
        business_id: str,
        category: str,
        amount_cents: int,
        receipt_ref: Optional[str] = None,
        actor: str = "system"
    ) -> Expense:
        if amount_cents <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense amount must be positive"
            )

        expense = Expense(
            business_id=business_id,
            category=category,
            amount=amount_cents,
            receipt_ref=receipt_ref,
            created_at=datetime.now(timezone.utc)
        )
        db.add(expense)

        audit = AuditLog(
            business_id=business_id,
            actor=actor,
            resource="expenses",
            purpose=f"Recorded expense '{category}': R{amount_cents / 100:.2f}"
        )
        db.add(audit)
        db.commit()
        db.refresh(expense)
        return expense

    @classmethod
    def get_sales_summary(
        cls,
        db: Session,
        business_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        query = db.query(Sale).filter(Sale.business_id == business_id)
        if start_date:
            query = query.filter(Sale.created_at >= start_date)
        if end_date:
            query = query.filter(Sale.created_at <= end_date)

        sales = query.all()
        total_count = len(sales)
        total_revenue = sum(s.total for s in sales)

        cash_rev = sum(s.total for s in sales if s.payment_type == "cash")
        card_rev = sum(s.total for s in sales if s.payment_type == "card")
        credit_rev = sum(s.total for s in sales if s.payment_type == "spaza_credit")

        exp_query = db.query(Expense).filter(Expense.business_id == business_id)
        if start_date:
            exp_query = exp_query.filter(Expense.created_at >= start_date)
        if end_date:
            exp_query = exp_query.filter(Expense.created_at <= end_date)
        
        expenses = exp_query.all()
        total_expenses = sum(e.amount for e in expenses)

        return {
            "total_sales_count": total_count,
            "total_revenue_cents": total_revenue,
            "total_revenue_zar": round(total_revenue / 100.0, 2),
            "cash_revenue_cents": cash_rev,
            "card_revenue_cents": card_rev,
            "credit_revenue_cents": credit_rev,
            "total_expenses_cents": total_expenses,
            "net_cash_flow_cents": total_revenue - total_expenses,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }
