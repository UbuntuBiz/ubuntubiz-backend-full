from app.database.connection import SessionLocal
from app.database.models import Business
from app.services.analytics_service import AnalyticsService
from app.core.logging import logger
from app.core.tenant import set_session_tenant


def run_detect_alerts():
    db = SessionLocal()
    try:
        active_businesses = db.query(Business).filter(Business.status == "active").all()
        logger.info(f"Running automated alert detection for {len(active_businesses)} businesses...")
        total_alerts = 0
        failures = []
        for biz in active_businesses:
            try:
                set_session_tenant(db, biz.id)
                alerts = AnalyticsService.detect_alerts(db, biz.id)
                total_alerts += len(alerts)
            except Exception as e:
                logger.error(
                    f"Alert detection failed for business {biz.id} ({type(e).__name__})"
                )
                db.rollback()
                failures.append(biz.id)
        if failures:
            raise RuntimeError(f"Alert detection failed for {len(failures)} businesses")
        logger.info(f"Alert detection finished. Generated {total_alerts} new alerts.")
    finally:
        db.close()


if __name__ == "__main__":
    run_detect_alerts()
