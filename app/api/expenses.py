from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import Expense, User
from app.schemas.sales import ExpenseCreate, ExpenseResponse
from app.services.sales_service import SalesService
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/expenses", tags=["Expense Tracking"])


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def record_expense(
    req: ExpenseCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Log an operating expense (transport, electricity, stock, etc.).
    """
    expense = SalesService.record_expense(
        db=db,
        business_id=current_user.business_id,
        category=req.category,
        amount_cents=req.amount,
        receipt_ref=req.receipt_ref,
        actor=current_user.id
    )
    return ExpenseResponse(
        id=expense.id,
        business_id=expense.business_id,
        category=expense.category,
        amount=expense.amount,
        amount_zar=round(expense.amount / 100.0, 2),
        receipt_ref=expense.receipt_ref,
        created_at=expense.created_at
    )


@router.get("", response_model=List[ExpenseResponse])
def list_expenses(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List business expenses.
    """
    expenses = db.query(Expense).filter(
        Expense.business_id == current_user.business_id
    ).order_by(Expense.created_at.desc()).offset(offset).limit(limit).all()

    return [
        ExpenseResponse(
            id=e.id,
            business_id=e.business_id,
            category=e.category,
            amount=e.amount,
            amount_zar=round(e.amount / 100.0, 2),
            receipt_ref=e.receipt_ref,
            created_at=e.created_at
        )
        for e in expenses
    ]
