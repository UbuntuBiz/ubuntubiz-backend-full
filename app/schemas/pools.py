from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class GroupRoundCreate(BaseModel):
    item_name: str = Field(..., min_length=2, max_length=255)
    target_quantity: int = Field(..., gt=0)
    target_cents: int = Field(..., gt=0)
    duration_days: int = Field(7, ge=1, le=30)


class PledgeCreate(BaseModel):
    quantity: int = Field(..., gt=0)
    amount_cents: int = Field(..., gt=0)


class PledgeResponse(BaseModel):
    id: str
    round_id: str
    business_id: str
    quantity: int
    amount_cents: int
    amount_zar: float
    payment_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BidResponse(BaseModel):
    id: str
    round_id: str
    supplier_id: str
    supplier_name: Optional[str] = None
    unit_price_cents: int
    unit_price_zar: float
    delivery_terms: Optional[str]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupRoundResponse(BaseModel):
    id: str
    initiator_business_id: str
    item_name: str
    target_quantity: int
    current_quantity: int
    target_cents: int
    target_zar: float
    current_cents: int
    current_zar: float
    progress_percent: float
    onchain_pool_id: Optional[str]
    status: str
    closes_at: Optional[datetime]
    created_at: datetime
    pledges: List[PledgeResponse] = []
    bids: List[BidResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    contact_phone: str = Field(..., min_length=10, max_length=15)
    area: str = Field(..., min_length=2, max_length=255)
    catalog_summary: Optional[str] = None
    is_verified: bool = False


class SupplierResponse(BaseModel):
    id: str
    name: str
    contact_phone: str
    area: str
    catalog_summary: Optional[str]
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
