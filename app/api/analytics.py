from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import DailyMetric, Alert, Sale, SaleItem, User
from app.schemas.analytics import (
    DailyMetricResponse,
    AlertResponse,
    ProfitSummaryResponse,
    StockHealthResponse,
    MorningBriefResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.sales_service import SalesService
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/analytics", tags=["Analytics & Business Intelligence"])


@router.get("/summary")
def get_analytics_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Overview of sales volume, revenue, expenses, and net cash flow.
    """
    return SalesService.get_sales_summary(
        db=db,
        business_id=current_user.business_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/daily", response_model=List[DailyMetricResponse])
def get_daily_metrics(
    target_date: Optional[date] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve or compute daily performance metrics (daily_sales, gross_profit, cash_variance).
    """
    query_date = target_date or datetime.now(timezone.utc).date()
    # Compute if not computed
    metrics = db.query(DailyMetric).filter(
        DailyMetric.business_id == current_user.business_id,
        DailyMetric.date == query_date
    ).all()

    if not metrics:
        metrics = AnalyticsService.compute_daily_metrics(db, current_user.business_id, query_date)

    return metrics


@router.get("/profit", response_model=ProfitSummaryResponse)
def get_profit_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Calculates total sales revenue, cost of goods sold, and gross profit margin.
    """
    end_d = end_date or datetime.now(timezone.utc).date()
    start_d = start_date or (end_d - timedelta(days=30))

    start_dt = datetime(start_d.year, start_d.month, start_d.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, tzinfo=timezone.utc)

    summary = SalesService.get_sales_summary(db, current_user.business_id, start_dt, end_dt)
    revenue_cents = summary["total_revenue_cents"]

    # Compute COGS from sale items
    sale_items = db.query(SaleItem).join(
        Sale,
        Sale.id == SaleItem.sale_id
    ).filter(
        Sale.business_id == current_user.business_id,
        Sale.created_at >= start_dt,
        Sale.created_at <= end_dt
    ).all()
    cogs_cents = sum(
        (item.unit_cost if item.unit_cost is not None else (item.product.cost_price or 0))
        * item.qty
        for item in sale_items
    )
    gross_profit_cents = revenue_cents - cogs_cents
    margin = round((gross_profit_cents / revenue_cents * 100.0), 1) if revenue_cents > 0 else 0.0

    return ProfitSummaryResponse(
        business_id=current_user.business_id,
        start_date=str(start_d),
        end_date=str(end_d),
        total_sales_cents=revenue_cents,
        total_sales_zar=round(revenue_cents / 100.0, 2),
        total_cost_cents=cogs_cents,
        total_cost_zar=round(cogs_cents / 100.0, 2),
        gross_profit_cents=gross_profit_cents,
        gross_profit_zar=round(gross_profit_cents / 100.0, 2),
        gross_margin_percent=margin
    )


@router.get("/stock", response_model=List[StockHealthResponse])
def get_stock_health(
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Calculates stock health, days of stock remaining, and identifies dead stock.
    """
    return AnalyticsService.get_stock_health(db, current_user.business_id)


@router.get("/alerts", response_model=List[AlertResponse])
def get_alerts(
    status_filter: Optional[str] = "active",
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List business alerts (stock-out risks, sales drops, cash variances).
    """
    # Trigger fresh alert evaluation
    AnalyticsService.detect_alerts(db, current_user.business_id)

    query = db.query(Alert).filter(Alert.business_id == current_user.business_id)
    if status_filter:
        query = query.filter(Alert.status == status_filter)

    return query.order_by(Alert.created_at.desc()).all()


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Mark an active alert as resolved or dismissed.
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.business_id == current_user.business_id
    ).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = "resolved"
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/morning-brief", response_model=MorningBriefResponse)
def get_morning_brief(
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Generate an authoritative, factual morning brief summarizing business performance.
    """
    return AnalyticsService.generate_morning_brief(db, current_user.business_id)
