"""Celery application."""
from __future__ import annotations

import os

from celery import Celery


def make_celery() -> Celery:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    app = Celery("sdr", broker=redis_url, backend=redis_url)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = make_celery()
