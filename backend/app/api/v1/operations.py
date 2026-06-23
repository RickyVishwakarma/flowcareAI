"""Insurance verification, appointment scheduling, and audit-log endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.operations import (
    Appointment,
    AuditLog,
    InsuranceVerification,
)
from app.models.organization import User
from app.models.referral import Referral
from app.services import insurance, scheduling

router = APIRouter(tags=["operations"])


# ── Insurance ──
class VerifyInsuranceRequest(BaseModel):
    referral_id: str
    provider: str | None = None
    member_id: str | None = None


def _owned_referral(db: Session, referral_id: str, user: User) -> Referral:
    referral = db.get(Referral, referral_id)
    if referral is None or referral.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral


@router.post("/verify-insurance")
def verify_insurance(
    payload: VerifyInsuranceRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    referral = _owned_referral(db, payload.referral_id, user)
    extracted = referral.extracted_data
    record = insurance.verify(
        db,
        referral_id=referral.id,
        provider=payload.provider or (extracted.insurance_provider if extracted else None),
        member_id=payload.member_id or (extracted.insurance_member_id if extracted else None),
    )
    db.commit()
    return {
        "id": record.id,
        "status": record.status.value if hasattr(record.status, "value") else record.status,
        "coverage_active": record.coverage_active,
        "eligibility": record.eligibility,
    }


@router.get("/referrals/{referral_id}/insurance")
def insurance_history(
    referral_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    _owned_referral(db, referral_id, user)
    rows = db.execute(
        select(InsuranceVerification)
        .where(InsuranceVerification.referral_id == referral_id)
        .order_by(InsuranceVerification.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": r.id,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "coverage_active": r.coverage_active,
            "eligibility": r.eligibility,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ── Appointments ──
class ScheduleRequest(BaseModel):
    referral_id: str
    provider_name: str | None = None
    when: datetime | None = None
    duration_minutes: int = 30


@router.post("/schedule-appointment")
def schedule_appointment(
    payload: ScheduleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned_referral(db, payload.referral_id, user)
    appt = scheduling.schedule(
        db,
        referral_id=payload.referral_id,
        provider_name=payload.provider_name,
        when=payload.when,
        duration_minutes=payload.duration_minutes,
    )
    db.commit()
    return {
        "id": appt.id,
        "scheduled_for": appt.scheduled_for,
        "provider_name": appt.provider_name,
        "status": appt.status.value if hasattr(appt.status, "value") else appt.status,
    }


@router.get("/referrals/{referral_id}/appointments")
def list_appointments(
    referral_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    _owned_referral(db, referral_id, user)
    rows = db.execute(
        select(Appointment).where(Appointment.referral_id == referral_id)
    ).scalars().all()
    return [
        {
            "id": a.id,
            "provider_name": a.provider_name,
            "scheduled_for": a.scheduled_for,
            "status": a.status.value if hasattr(a.status, "value") else a.status,
        }
        for a in rows
    ]


# ── Audit ──
@router.get("/audit-logs")
def audit_logs(
    referral_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == user.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 500))
    )
    if referral_id:
        stmt = stmt.where(AuditLog.referral_id == referral_id)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "actor": r.actor,
            "referral_id": r.referral_id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "detail": r.detail,
            "created_at": r.created_at,
        }
        for r in rows
    ]
