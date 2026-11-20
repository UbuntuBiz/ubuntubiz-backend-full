from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import (
    Sale,
    SaleItem,
    Expense,
    Product,
    StockLevel,
    DailyMetric,
    Alert,
    Business,
)
from app.core.logging import logger


class AnalyticsService:
    @classmethod
    def compute_daily_metrics(cls, db: Session, business_id: str, target_date: date) -> List[DailyMetric]:
        """
        Computes financial and stock velocity metrics for a business on target_date:
        - daily_sales
        - gross_profit
        - cash_variance
        """
        date_str = str(target_date)

        # 1. Total Daily Sales (using func.date for cross-dialect SQLite & PostgreSQL compatibility)
        sales = db.query(Sale).filter(
            Sale.business_id == business_id,
            func.date(Sale.created_at) == date_str
        ).all()
        daily_sales_cents = sum(s.total for s in sales)

        # 2. Total COGS & Gross Profit
        sale_ids = [s.id for s in sales]
        items = db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).all() if sale_ids else []
        total_cogs_cents = 0
        for item in items:
            cost = item.product.cost_price if item.product and item.product.cost_price is not None else 0
            total_cogs_cents += cost * item.qty
        gross_profit_cents = daily_sales_cents - total_cogs_cents

        # 3. Expenses & Cash Variance
        expenses = db.query(Expense).filter(
            Expense.business_id == business_id,
            func.date(Expense.created_at) == date_str
        ).all()
        total_expenses_cents = sum(e.amount for e in expenses)
        cash_sales_cents = sum(s.total for s in sales if s.payment_type == "cash")
        cash_variance_cents = cash_sales_cents - total_expenses_cents

        # Upsert or save metrics
        metrics_to_record = [
            ("daily_sales", float(daily_sales_cents)),
            ("gross_profit", float(gross_profit_cents)),
            ("total_expenses", float(total_expenses_cents)),
            ("cash_variance", float(cash_variance_cents)),
        ]

        saved_metrics = []
        for metric_name, val in metrics_to_record:
            metric_row = db.query(DailyMetric).filter(
                DailyMetric.business_id == business_id,
                DailyMetric.date == target_date,
                DailyMetric.metric == metric_name,
                DailyMetric.product_id.is_(None)
            ).first()

            if not metric_row:
                metric_row = DailyMetric(
                    business_id=business_id,
                    date=target_date,
                    metric=metric_name,
                    value=val,
                    is_estimate=False,
                    computed_at=datetime.now(timezone.utc)
                )
                db.add(metric_row)
            else:
                metric_row.value = val
                metric_row.computed_at = datetime.now(timezone.utc)
            saved_metrics.append(metric_row)

        db.commit()
        return saved_metrics

    @classmethod
    def detect_alerts(
        cls,
        db: Session,
        business_id: str,
        lead_time_days: int = 3,
        drop_threshold_ratio: float = 0.6,
        max_alerts_per_day: int = 5
    ) -> List[Alert]:
        """
        Evaluates heuristic alert triggers:
        1. Low stock risk: days of stock < lead time
        2. Sales drop: today's sales < 60% of historical median for same weekday
        Caps active alerts per business per day.
        """
        new_alerts = []
        today = datetime.now(timezone.utc).date()

        # Check existing active alerts today
        start_today = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
        existing_today_count = db.query(Alert).filter(
            Alert.business_id == business_id,
            Alert.created_at >= start_today
        ).count()

        if existing_today_count >= max_alerts_per_day:
            return []

        # Rule 1: Low stock risk based on stock vs reorder point
        products = db.query(Product).filter(Product.business_id == business_id).all()
        for prod in products:
            qty = prod.stock_level.qty_on_hand if prod.stock_level else 0
            if qty <= prod.reorder_point:
                # Check if active alert already exists for this product
                already_alerted = db.query(Alert).filter(
                    Alert.business_id == business_id,
                    Alert.product_id == prod.id,
                    Alert.status == "active",
                    Alert.type == "low_stock_risk"
                ).first()
                if not already_alerted and (existing_today_count + len(new_alerts)) < max_alerts_per_day:
                    alert = Alert(
                        business_id=business_id,
                        type="low_stock_risk",
                        product_id=prod.id,
                        message=f"Critical stock: '{prod.name}' has {qty} {prod.unit}s remaining (reorder point: {prod.reorder_point})",
                        status="active"
                    )
                    db.add(alert)
                    new_alerts.append(alert)

        # Rule 2: Sales Drop vs Historical Weekday
        weekday = today.weekday()
        # Find past sales for same weekday over last 4 weeks
        past_weekday_sales = []
        for w in range(1, 5):
            past_date = today - timedelta(days=7 * w)
            m = db.query(DailyMetric).filter(
                DailyMetric.business_id == business_id,
                DailyMetric.date == past_date,
                DailyMetric.metric == "daily_sales"
            ).first()
            if m:
                past_weekday_sales.append(m.value)

        if len(past_weekday_sales) >= 2:
            past_weekday_sales.sort()
            median_sales = past_weekday_sales[len(past_weekday_sales) // 2]
            today_sales_metric = db.query(DailyMetric).filter(
                DailyMetric.business_id == business_id,
                DailyMetric.date == today,
                DailyMetric.metric == "daily_sales"
            ).first()
            today_sales = today_sales_metric.value if today_sales_metric else 0

            if median_sales > 0 and (today_sales / median_sales) < drop_threshold_ratio:
                already_drop_alert = db.query(Alert).filter(
                    Alert.business_id == business_id,
                    Alert.type == "sales_drop",
                    Alert.created_at >= start_today
                ).first()
                if not already_drop_alert and (existing_today_count + len(new_alerts)) < max_alerts_per_day:
                    alert = Alert(
                        business_id=business_id,
                        type="sales_drop",
                        product_id=None,
                        message=(
                            f"Sales drop detected: Today's sales (R{today_sales / 100:.2f}) are under 60% "
                            f"of normal weekday average (R{median_sales / 100:.2f})"
                        ),
                        status="active"
                    )
                    db.add(alert)
                    new_alerts.append(alert)

        db.commit()
        return new_alerts

    @classmethod
    def get_stock_health(cls, db: Session, business_id: str) -> List[Dict[str, Any]]:
        """
        Calculates 30-day velocity, days of stock, and categorizes status
        (healthy, low_stock, stockout, dead_stock).
        """
        products = db.query(Product).filter(Product.business_id == business_id).all()
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        health_list = []
        for prod in products:
            qty = prod.stock_level.qty_on_hand if prod.stock_level else 0

            # 30-day sale count
            sales_count = db.query(func.sum(SaleItem.qty)).join(
                Sale, Sale.id == SaleItem.sale_id
            ).filter(
                SaleItem.product_id == prod.id,
                Sale.business_id == business_id,
                Sale.created_at >= thirty_days_ago
            ).scalar() or 0

            avg_daily_sales = round(sales_count / 30.0, 2)
            if avg_daily_sales > 0:
                days_of_stock = round(qty / avg_daily_sales, 1)
            else:
                days_of_stock = 999.0 if qty > 0 else 0.0

            if qty == 0:
                status_cat = "stockout"
            elif sales_count == 0 and qty > 0:
                status_cat = "dead_stock"
            elif qty <= prod.reorder_point or days_of_stock < 3.0:
                status_cat = "low_stock"
            else:
                status_cat = "healthy"

            health_list.append({
                "product_id": prod.id,
                "product_name": prod.name,
                "qty_on_hand": qty,
                "avg_daily_sales": avg_daily_sales,
                "days_of_stock": days_of_stock,
                "reorder_point": prod.reorder_point,
                "status": status_cat
            })

        return health_list

    @classmethod
    def generate_morning_brief(cls, db: Session, business_id: str) -> Dict[str, Any]:
        """
        Synthesizes yesterday's business brief strictly from database records.
        """
        biz = db.query(Business).filter(Business.id == business_id).first()
        biz_name = biz.name if biz else "Your Spaza Shop"

        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        yesterday_str = str(yesterday)

        yesterday_sales = db.query(Sale).filter(
            Sale.business_id == business_id,
            func.date(Sale.created_at) == yesterday_str
        ).all()

        total_sales_cents = sum(s.total for s in yesterday_sales)
        yesterday_sales_zar = round(total_sales_cents / 100.0, 2)

        # Gross profit
        sale_ids = [s.id for s in yesterday_sales]
        items = db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).all() if sale_ids else []
        cogs_cents = sum((it.product.cost_price or 0) * it.qty for it in items)
        gross_profit_zar = round((total_sales_cents - cogs_cents) / 100.0, 2)

        # Active alerts
        active_alerts = db.query(Alert).filter(
            Alert.business_id == business_id,
            Alert.status == "active"
        ).all()

        # Low stock items
        low_stock_products = [
            p.name for p in db.query(Product).filter(Product.business_id == business_id).all()
            if (p.stock_level and p.stock_level.qty_on_hand <= p.reorder_point)
        ]

        narrative = (
            f"Good morning {biz_name}! Yesterday you recorded R{yesterday_sales_zar:.2f} across "
            f"{len(yesterday_sales)} sales with an estimated gross profit of R{gross_profit_zar:.2f}. "
            f"You have {len(low_stock_products)} low-stock products requiring restock, and "
            f"{len(active_alerts)} active operational alerts."
        )

        return {
            "business_id": business_id,
            "business_name": biz_name,
            "brief_date": str(yesterday),
            "yesterday_sales_zar": yesterday_sales_zar,
            "yesterday_gross_profit_zar": gross_profit_zar,
            "active_alerts_count": len(active_alerts),
            "low_stock_items": low_stock_products,
            "narrative": narrative
        }
