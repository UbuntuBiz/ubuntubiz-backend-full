from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class DailyMetricResponse(BaseModel):
    id: str
    business_id: str
    date: date
    product_id: Optional[str]
    metric: str
    value: float
    is_estimate: bool
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertResponse(BaseModel):
    id: str
    business_id: str
    type: str
    product_id: Optional[str]
    message: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfitSummaryResponse(BaseModel):
    business_id: str
    start_date: str
    end_date: str
    total_sales_cents: int
    total_sales_zar: float
    total_cost_cents: int
    total_cost_zar: float
    gross_profit_cents: int
    gross_profit_zar: float
    gross_margin_percent: float


class StockHealthResponse(BaseModel):
    product_id: str
    product_name: str
    qty_on_hand: int
    avg_daily_sales: float
    days_of_stock: float
    reorder_point: int
    status: str  # healthy, low_stock, stockout, dead_stock


class MorningBriefResponse(BaseModel):
    business_id: str
    business_name: str
    brief_date: str
    yesterday_sales_zar: float
    yesterday_gross_profit_zar: float
    active_alerts_count: int
    low_stock_items: List[str]
    narrative: str
