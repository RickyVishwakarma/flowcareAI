"""Dashboard analytics — organization-scoped aggregates over referral data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import ExecutionStatus, ReferralStatus
from app.models.operations import Appointment, InsuranceVerification, Task
from app.models.referral import ExtractedData, Referral
from app.models.workflow import Workflow, WorkflowExecution

TIMESERIES_DAYS = 14


def _counts(db: Session, column, *wheres) -> dict[str, int]:
    stmt = select(column, func.count()).group_by(column)
    for w in wheres:
        stmt = stmt.where(w)
    return {str(k): int(v) for k, v in db.execute(stmt).all() if k is not None}


def overview(db: Session, organization_id: str) -> dict:
    org = Referral.organization_id == organization_id

    # ── Referrals ──
    referrals_by_status = _counts(db, Referral.status, org)
    referrals_by_source = _counts(db, Referral.source, org)
    referrals_total = sum(referrals_by_status.values())

    # Daily time series (last N days), bucketed in Python for DB portability.
    created = db.execute(select(Referral.created_at).where(org)).scalars().all()
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=TIMESERIES_DAYS - 1)
    buckets = {(start + timedelta(days=i)).isoformat(): 0 for i in range(TIMESERIES_DAYS)}
    for ts in created:
        d = ts.date().isoformat()
        if d in buckets:
            buckets[d] += 1
    timeseries = [{"date": k, "count": v} for k, v in buckets.items()]

    # ── Extraction / validation ──
    validation_breakdown = _counts(
        db,
        ExtractedData.validation_status,
        ExtractedData.referral_id == Referral.id,
        org,
    )
    extractor_breakdown = _counts(
        db, ExtractedData.extractor, ExtractedData.referral_id == Referral.id, org
    )
    avg_conf = db.execute(
        select(func.avg(ExtractedData.overall_confidence))
        .where(ExtractedData.referral_id == Referral.id, org)
    ).scalar()

    # ── Workflows ──
    wf_by_status = _counts(
        db,
        WorkflowExecution.status,
        WorkflowExecution.workflow_id == Workflow.id,
        Workflow.organization_id == organization_id,
    )
    wf_total = sum(wf_by_status.values())
    wf_success = wf_by_status.get(ExecutionStatus.SUCCEEDED.value, 0)

    # ── Insurance ──
    ins_total = db.execute(
        select(func.count())
        .select_from(InsuranceVerification)
        .where(InsuranceVerification.referral_id == Referral.id, org)
    ).scalar() or 0
    ins_active = db.execute(
        select(func.count())
        .select_from(InsuranceVerification)
        .where(
            InsuranceVerification.referral_id == Referral.id,
            InsuranceVerification.coverage_active.is_(True),
            org,
        )
    ).scalar() or 0

    appointments_total = db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.referral_id == Referral.id, org)
    ).scalar() or 0

    open_tasks = db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.organization_id == organization_id, Task.status == "open")
    ).scalar() or 0

    return {
        "referrals_total": referrals_total,
        "referrals_by_status": referrals_by_status,
        "referrals_by_source": referrals_by_source,
        "referrals_timeseries": timeseries,
        "validation_breakdown": validation_breakdown,
        "extractor_breakdown": extractor_breakdown,
        "avg_confidence": round(float(avg_conf), 3) if avg_conf is not None else None,
        "workflow_total": wf_total,
        "workflow_by_status": wf_by_status,
        "workflow_success_rate": round(wf_success / wf_total, 3) if wf_total else 0.0,
        "insurance_total": int(ins_total),
        "insurance_active": int(ins_active),
        "insurance_active_rate": round(ins_active / ins_total, 3) if ins_total else 0.0,
        "appointments_total": int(appointments_total),
        "review_queue_size": referrals_by_status.get(ReferralStatus.NEEDS_REVIEW.value, 0),
        "open_tasks": int(open_tasks),
    }
