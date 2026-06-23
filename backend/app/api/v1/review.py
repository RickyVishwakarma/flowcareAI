"""Human-in-the-loop review queue endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.base import UserRole
from app.models.organization import User
from app.models.referral import Referral
from app.schemas.review import (
    ReviewDetail,
    ReviewQueueItem,
    ReviewResult,
    ReviewSubmission,
)
from app.services import review
from app.services.extraction import EXTRACTION_FIELDS

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/queue", response_model=list[ReviewQueueItem])
def review_queue(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ReviewQueueItem]:
    items = []
    for referral in review.queue(db, user.organization_id):
        report = (
            referral.extracted_data.validation_report if referral.extracted_data else {}
        )
        items.append(
            ReviewQueueItem(
                id=referral.id,
                reference_code=referral.reference_code,
                status=referral.status.value if hasattr(referral.status, "value") else referral.status,
                patient_name=referral.patient_name,
                created_at=referral.created_at,
                error_count=len(report.get("errors", [])),
                warning_count=len(report.get("warnings", [])),
            )
        )
    return items


def _owned(db: Session, referral_id: str, user: User) -> Referral:
    referral = db.get(Referral, referral_id)
    if referral is None or referral.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral


@router.get("/{referral_id}", response_model=ReviewDetail)
def review_detail(
    referral_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ReviewDetail:
    referral = _owned(db, referral_id, user)
    extracted = referral.extracted_data
    document = referral.documents[0] if referral.documents else None
    return ReviewDetail(
        id=referral.id,
        reference_code=referral.reference_code,
        status=referral.status.value if hasattr(referral.status, "value") else referral.status,
        ocr_text=document.ocr_text if document else None,
        fields={f: (getattr(extracted, f) if extracted else None) for f in EXTRACTION_FIELDS},
        field_confidence=extracted.field_confidence if extracted else {},
        validation_report=extracted.validation_report if extracted else {},
    )


@router.post("/{referral_id}", response_model=ReviewResult)
def submit_review(
    referral_id: str,
    payload: ReviewSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.AGENT)),
) -> ReviewResult:
    referral = _owned(db, referral_id, user)
    corrections = payload.model_dump(exclude={"rerun_workflow"})
    result = review.apply_review(
        db,
        referral=referral,
        corrections=corrections,
        reviewer_id=user.id,
        rerun_workflow=payload.rerun_workflow,
    )
    return ReviewResult(**result)
