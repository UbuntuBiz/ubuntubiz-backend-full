from app.core.celery_config import celery_app
from app.jobs.alerts import run_detect_alerts
from app.jobs.daily_metrics import run_compute_daily_metrics
from app.jobs.morning_brief import run_morning_briefs


@celery_app.task(
    name="app.jobs.tasks.compute_daily_metrics",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def compute_daily_metrics_task() -> None:
    run_compute_daily_metrics()


@celery_app.task(
    name="app.jobs.tasks.detect_alerts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def detect_alerts_task() -> None:
    run_detect_alerts()


@celery_app.task(
    name="app.jobs.tasks.generate_morning_briefs",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def generate_morning_briefs_task() -> list[dict]:
    return run_morning_briefs()
