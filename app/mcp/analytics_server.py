from typing import Dict, Any, List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.services.analytics_service import AnalyticsService
from app.services.sales_service import SalesService
from app.database.models import DailyMetric, Alert


class AnalyticsMCPServer:
    """
    Model Context Protocol (MCP) tool provider for Business Analytics.
    """

    @classmethod
    def get_metric(
        cls,
        db: Session,
        business_id: str,
        name: str,
        target_date: Optional[str] = None
    ) -> Dict[str, Any]:
        calc_date = date.fromisoformat(target_date) if target_date else date.today()
        metric = db.query(DailyMetric).filter(
            DailyMetric.business_id == business_id,
            DailyMetric.date == calc_date,
            DailyMetric.metric == name
        ).first()

        if not metric:
            # Trigger compute
            AnalyticsService.compute_daily_metrics(db, business_id, calc_date)
            metric = db.query(DailyMetric).filter(
                DailyMetric.business_id == business_id,
                DailyMetric.date == calc_date,
                DailyMetric.metric == name
            ).first()

        return {
            "metric": name,
            "date": str(calc_date),
            "value": metric.value if metric else 0.0
        }

    @classmethod
    def get_sales_summary(
        cls,
        db: Session,
        business_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        return SalesService.get_sales_summary(db, business_id, start_dt, end_dt)

    @classmethod
    def list_alerts(
        cls,
        db: Session,
        business_id: str,
        status_filter: str = "active"
    ) -> List[Dict[str, Any]]:
        AnalyticsService.detect_alerts(db, business_id)
        alerts = db.query(Alert).filter(
            Alert.business_id == business_id,
            Alert.status == status_filter
        ).all()
        return [
            {
                "id": a.id,
                "type": a.type,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat()
            }
            for a in alerts
        ]
