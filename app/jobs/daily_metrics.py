from datetime import date, timedelta
from app.database.connection import SessionLocal
from app.database.models import Business
from app.services.analytics_service import AnalyticsService
from app.core.logging import logger


def run_compute_daily_metrics(target_date: date = None):
    calc_date = target_date or (date.today() - timedelta(days=1))
    db = SessionLocal()
    try:
        active_businesses = db.query(Business).filter(Business.status == "active").all()
        logger.info(f"Running daily metrics job for {len(active_businesses)} businesses on {calc_date}...")
        for biz in active_businesses:
            try:
                AnalyticsService.compute_daily_metrics(db, biz.id, calc_date)
            except Exception as e:
                logger.error(f"Error computing daily metrics for business {biz.id}: {e}")
        logger.info("Daily metrics computation completed.")
    finally:
        db.close()


if __name__ == "__main__":
    run_compute_daily_metrics()
