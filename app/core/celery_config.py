"""Celery configuration for UbuntuBiz backend

This module defines the Celery app used for background processing such as
scheduled jobs (daily metrics, alerts, morning brief) and any long‑running
tasks.  The configuration mirrors the settings in ``app.config``.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

# Create Celery instance
celery_app = Celery(
    "ubuntubiz",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Basic configuration – tasks will autodetect modules under ``app.jobs``
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Johannesburg",
    enable_utc=False,
    beat_schedule={
        "compute-daily-metrics": {
            "task": "app.jobs.tasks.compute_daily_metrics",
            "schedule": crontab(hour=0, minute=15),
        },
        "detect-alerts": {
            "task": "app.jobs.tasks.detect_alerts",
            "schedule": crontab(minute="*/30"),
        },
        "generate-morning-briefs": {
            "task": "app.jobs.tasks.generate_morning_briefs",
            "schedule": crontab(hour=6, minute=0),
        },
    },
    task_routes={
        "app.jobs.*": {"queue": "default"},
    },
)

# Auto‑discover tasks in the ``app.jobs`` package
celery_app.autodiscover_tasks(["app.jobs"])

# Example task to verify the worker is running (can be called via ``celery -A app.core.celery_config.celery_app call app.core.celery_config.celery_app.ping``)
@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
