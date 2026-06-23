"""Celery application factory."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "flowcare",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

# When no real broker is configured (local dev / tests), run tasks inline so the
# pipeline still completes end-to-end without a worker process.
_eager = settings.celery_broker_url.startswith("memory://") or settings.environment == "test"

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_always_eager=_eager,
    task_eager_propagates=_eager,
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.process_referral_task": {"queue": "ingest"},
        "app.workers.tasks.run_workflow_execution": {"queue": "workflows"},
    },
)
