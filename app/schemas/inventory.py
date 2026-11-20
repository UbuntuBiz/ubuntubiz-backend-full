from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    unit: str = Field("item", description="item, kg, litre, loaf, pack")
    cost_price: Optional[int] = Field(None, ge=0, description="Cost price in integer cents (e.g. 1500 for R15.00)")
    sell_price: int = Field(..., ge=0, description="Selling price in integer cents")
    reorder_point: int = Field(5, ge=0)
    expiry_tracked: bool = Field(False)
    aliases: Optional[List[str]] = Field(default_factory=list, description="Common township colloquial names / aliases")
    initial_stock: Optional[int] = Field(0, ge=0, description="Initial stock level")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    unit: Optional[str] = None
    cost_price: Optional[int] = Field(None, ge=0)
    sell_price: Optional[int] = Field(None, ge=0)
    reorder_point: Optional[int] = Field(None, ge=0)
    expiry_tracked: Optional[bool] = None


class ProductResponse(BaseModel):
    id: str
    business_id: str
    name: str
    unit: str
    cost_price: Optional[int]
    sell_price: int
    reorder_point: int
    expiry_tracked: bool
    created_at: datetime
    qty_on_hand: int = 0
    aliases: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class InventoryEventCreate(BaseModel):
    product_id: str
    type: str = Field(..., description="purchase, adjustment, delivery, damage, shrinkage")
    qty_delta: int = Field(..., description="Positive for stock addition, negative for deduction")
    unit_cost: Optional[int] = Field(None, ge=0)
    unit_price: Optional[int] = Field(None, ge=0)
    reason: str = Field(..., min_length=2, max_length=255)
    idempotency_key: str = Field(..., min_length=4, max_length=128)


class InventoryEventResponse(BaseModel):
    id: str
    business_id: str
    product_id: str
    type: str
    qty_delta: int
    unit_cost: Optional[int]
    unit_price: Optional[int]
    actor: str
    reason: str
    trace_id: str
    idempotency_key: str
    reverses_event_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockLevelResponse(BaseModel):
    product_id: str
    product_name: str
    qty_on_hand: int
    reorder_point: int
    is_low_stock: bool
    unit: str
    sell_price: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
