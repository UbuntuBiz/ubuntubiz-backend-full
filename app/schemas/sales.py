from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SaleItemCreate(BaseModel):
    product_id: str
    qty: int = Field(..., gt=0)
    unit_price: Optional[int] = Field(None, ge=0, description="Override unit price in cents, or defaults to product sell_price")


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(..., min_length=1)
    payment_type: str = Field("cash", description="cash, card, spaza_credit, crypto")
    idempotency_key: str = Field(..., min_length=4, max_length=128)


class SaleItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: Optional[str] = None
    qty: int
    unit_price: int

    model_config = ConfigDict(from_attributes=True)


class SaleResponse(BaseModel):
    id: str
    business_id: str
    total: int  # in integer cents
    total_zar: float  # formatted in ZAR (e.g. 15.50)
    payment_type: str
    created_at: datetime
    items: List[SaleItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ExpenseCreate(BaseModel):
    category: str = Field(..., min_length=2, max_length=64, description="transport, electricity, stock, rent, municipal")
    amount: int = Field(..., gt=0, description="Expense amount in integer cents")
    receipt_ref: Optional[str] = Field(None, max_length=128)


class ExpenseResponse(BaseModel):
    id: str
    business_id: str
    category: str
    amount: int
    amount_zar: float
    receipt_ref: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalesSummaryResponse(BaseModel):
    total_sales_count: int
    total_revenue_cents: int
    total_revenue_zar: float
    cash_revenue_cents: int
    card_revenue_cents: int
    credit_revenue_cents: int
    total_expenses_cents: int
    net_cash_flow_cents: int
    start_date: Optional[str]
    end_date: Optional[str]
