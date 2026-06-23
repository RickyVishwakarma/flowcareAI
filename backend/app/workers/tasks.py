"""Celery tasks with retry, exponential backoff, and a dead-letter queue.

Retry ladder:  attempt 1 → 2 → 3 → DLQ
On final failure the entity is marked failed/dead_letter and an audit row is
written so nothing is lost silently.
"""
from __future__ import annotations

from celery import Task

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.base import ExecutionStatus, ReferralStatus
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

MAX_RETRIES = 2  # → 3 total attempts before DLQ
RETRY_BACKOFF_BASE = 5  # seconds: 5, 10, 20…


class _DBTask(Task):
    """Base task that opens/closes a DB session per run."""

    abstract = True


@celery_app.task(
    bind=True,
    base=_DBTask,
    name="app.workers.tasks.process_referral_task",
    max_retries=MAX_RETRIES,
    acks_late=True,
)
def process_referral_task(self, referral_id: str) -> dict:
    from app.services.pipeline import process_referral

    db = SessionLocal()
    try:
        return process_referral(db, referral_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "process_referral failed (attempt %s/%s): %s",
            self.request.retries + 1,
            MAX_RETRIES + 1,
            exc,
            extra={"referral_id": referral_id},
        )
        if self.request.retries >= MAX_RETRIES:
            _to_dead_letter(db, referral_id, str(exc))
            raise
        raise self.retry(exc=exc, countdown=RETRY_BACKOFF_BASE * (2**self.request.retries))
    finally:
        db.close()


@celery_app.task(
    bind=True,
    base=_DBTask,
    name="app.workers.tasks.run_workflow_execution",
    max_retries=MAX_RETRIES,
    acks_late=True,
)
def run_workflow_execution(self, execution_id: str) -> dict:
    from app.models.workflow import WorkflowExecution
    from app.services.workflow_engine import run_execution

    db = SessionLocal()
    try:
        execution = db.get(WorkflowExecution, execution_id)
        if execution is None:
            return {"execution_id": execution_id, "status": "not_found"}
        run_execution(db, execution)
        db.commit()
        return {"execution_id": execution_id, "status": execution.status.value}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if self.request.retries >= MAX_RETRIES:
            _execution_to_dlq(db, execution_id, str(exc))
            raise
        raise self.retry(exc=exc, countdown=RETRY_BACKOFF_BASE * (2**self.request.retries))
    finally:
        db.close()


def _to_dead_letter(db, referral_id: str, error: str) -> None:
    from app.models.referral import Referral
    from app.services import audit

    referral = db.get(Referral, referral_id)
    if referral:
        referral.status = ReferralStatus.FAILED
        audit.record(
            db,
            action="referral.dead_letter",
            organization_id=referral.organization_id,
            referral_id=referral.id,
            entity_type="referral",
            entity_id=referral.id,
            detail={"error": error},
        )
        db.commit()


def _execution_to_dlq(db, execution_id: str, error: str) -> None:
    from app.models.workflow import WorkflowExecution
    from app.services import audit

    execution = db.get(WorkflowExecution, execution_id)
    if execution:
        execution.status = ExecutionStatus.DEAD_LETTER
        execution.error = error
        audit.record(
            db,
            action="workflow.dead_letter",
            referral_id=execution.referral_id,
            entity_type="workflow_execution",
            entity_id=execution.id,
            detail={"error": error},
        )
        db.commit()
