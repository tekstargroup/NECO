"""
Celery App Configuration - Sprint 12

Celery app for async analysis orchestration.
"""

from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "neco",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.analysis", "app.tasks.regulatory"]
)

# Celery Beat schedule - GAP 5 per-source scheduling
celery_app.conf.beat_schedule = {
    "poll-csms-5min": {
        "task": "app.tasks.regulatory.poll_regulatory_feeds",
        "schedule": 300.0,  # 5 min
        "kwargs": {"frequency_filter": "5min"},
    },
    "poll-federal-register-15min": {
        "task": "app.tasks.regulatory.poll_regulatory_feeds",
        "schedule": 900.0,  # 15 min
        "kwargs": {"frequency_filter": "15min"},
    },
    "poll-hourly": {
        "task": "app.tasks.regulatory.poll_regulatory_feeds",
        "schedule": 3600.0,  # 1h
        "kwargs": {"frequency_filter": "1h"},
    },
    "poll-6h": {
        "task": "app.tasks.regulatory.poll_regulatory_feeds",
        "schedule": 21600.0,  # 6h
        "kwargs": {"frequency_filter": "6h"},
    },
    "poll-daily": {
        "task": "app.tasks.regulatory.poll_regulatory_feeds",
        "schedule": 86400.0,  # 1d
        "kwargs": {"frequency_filter": "1d"},
    },
    "process-regulatory-signals": {
        "task": "app.tasks.regulatory.process_regulatory_signals",
        "schedule": 3700.0,  # Every hour, 100s after poll
        "kwargs": {"limit": 50},
    },
    "refresh-importer-hts-usage": {
        "task": "app.tasks.regulatory.refresh_importer_hts_usage",
        "schedule": 86400.0,  # Daily (Tier 8 internal data)
    },
}

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 min soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
