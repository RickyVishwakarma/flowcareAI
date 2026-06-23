"""Referral intake and retrieval endpoints."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.metrics import referrals_received
from app.models.base import ReferralSource, ReferralStatus
from app.models.organization import User
from app.models.referral import ExtractedData, Referral, ReferralDocument
from app.schemas.referral import (
    ReferralAccepted,
    ReferralDetail,
    ReferralFormSubmission,
    ReferralOut,
)
from app.services import audit, storage

router = APIRouter(prefix="/referrals", tags=["referrals"])

_SOURCE_BY_CONTENT = {
    "application/pdf": ReferralSource.PDF,
    "image/png": ReferralSource.IMAGE,
    "image/jpeg": ReferralSource.IMAGE,
    "image/tiff": ReferralSource.IMAGE,
}


def _new_reference_code() -> str:
    return "REF-" + secrets.token_hex(4).upper()


def _enqueue(referral_id: str) -> None:
    """Hand the referral to the task queue (eager in dev, async in prod)."""
    from app.workers.tasks import process_referral_task

    process_referral_task.delay(referral_id)


@router.post("", response_model=ReferralAccepted, status_code=status.HTTP_202_ACCEPTED)
def upload_referral(
    file: UploadFile = File(...),
    source: ReferralSource | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReferralAccepted:
    """Upload a referral document (PDF / image / fax). Kicks off async processing."""
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    resolved_source = source or _SOURCE_BY_CONTENT.get(
        file.content_type or "", ReferralSource.PDF
    )
    storage_key = storage.store(content, file.filename or "referral")

    referral = Referral(
        organization_id=user.organization_id,
        reference_code=_new_reference_code(),
        source=resolved_source,
        status=ReferralStatus.RECEIVED,
        created_by=user.id,
    )
    db.add(referral)
    db.flush()

    document = ReferralDocument(
        referral_id=referral.id,
        filename=file.filename or "referral",
        content_type=file.content_type,
        storage_key=storage_key,
        size_bytes=len(content),
    )
    db.add(document)
    audit.record(
        db,
        action="referral.uploaded",
        actor=user.id,
        organization_id=user.organization_id,
        referral_id=referral.id,
        entity_type="referral",
        entity_id=referral.id,
        detail={"filename": document.filename, "source": resolved_source.value},
    )
    db.commit()

    referrals_received.labels(source=resolved_source.value).inc()
    _enqueue(referral.id)
    return ReferralAccepted(
        id=referral.id, reference_code=referral.reference_code, status=referral.status
    )


@router.post("/form", response_model=ReferralAccepted, status_code=status.HTTP_202_ACCEPTED)
def submit_form(
    payload: ReferralFormSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReferralAccepted:
    """Submit a structured web-form referral (skips OCR, still validated)."""
    text = "\n".join(
        f"{k.replace('_', ' ').title()}: {v}"
        for k, v in payload.model_dump().items()
        if v
    )
    storage_key = storage.store(text.encode(), "form_submission.txt")

    referral = Referral(
        organization_id=user.organization_id,
        reference_code=_new_reference_code(),
        source=ReferralSource.WEB_FORM,
        status=ReferralStatus.RECEIVED,
        created_by=user.id,
    )
    db.add(referral)
    db.flush()
    db.add(
        ReferralDocument(
            referral_id=referral.id,
            filename="form_submission.txt",
            content_type="text/plain",
            storage_key=storage_key,
            size_bytes=len(text),
        )
    )
    db.commit()

    referrals_received.labels(source=ReferralSource.WEB_FORM.value).inc()
    _enqueue(referral.id)
    return ReferralAccepted(
        id=referral.id, reference_code=referral.reference_code, status=referral.status
    )


@router.get("", response_model=list[ReferralOut])
def list_referrals(
    status_filter: ReferralStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Referral]:
    stmt = (
        select(Referral)
        .where(Referral.organization_id == user.organization_id)
        .order_by(Referral.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    if status_filter:
        stmt = stmt.where(Referral.status == status_filter)
    return list(db.execute(stmt).scalars().all())


@router.get("/{referral_id}", response_model=ReferralDetail)
def get_referral(
    referral_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Referral:
    referral = db.get(Referral, referral_id)
    if referral is None or referral.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral
