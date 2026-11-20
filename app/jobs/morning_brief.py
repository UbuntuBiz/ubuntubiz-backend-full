from app.database.connection import SessionLocal
from app.database.models import Business
from app.services.analytics_service import AnalyticsService
from app.core.logging import logger


def run_morning_briefs():
    db = SessionLocal()
    try:
        active_businesses = db.query(Business).filter(Business.status == "active").all()
        logger.info(f"Generating morning briefs for {len(active_businesses)} businesses...")
        briefs = []
        for biz in active_businesses:
            try:
                brief = AnalyticsService.generate_morning_brief(db, biz.id)
                briefs.append(brief)
                logger.info(f"Morning brief for '{biz.name}': {brief['narrative']}")
            except Exception as e:
                logger.error(f"Error generating morning brief for business {biz.id}: {e}")
        return briefs
    finally:
        db.close()


if __name__ == "__main__":
    run_morning_briefs()
