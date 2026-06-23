"""Human-in-the-loop review.

Referrals whose extraction fails validation land in ``needs_review``. A reviewer
corrects the extracted fields; this service re-validates the corrected data,
updates status, records who changed what in the audit trail, and (optionally)
re-fires the workflow now that the data is clean.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import ReferralStatus, ValidationStatus
from app.models.referral import Referral
from app.services import audit, workflow_engine
from app.services.extraction import EXTRACTION_FIELDS, ExtractionResult
from app.services.validation import validate


def queue(db: Session, organization_id: str, limit: int = 50) -> list[Referral]:
    """Referrals awaiting human review, newest first."""
    stmt = (
        select(Referral)
        .where(
            Referral.organization_id == organization_id,
            Referral.status == ReferralStatus.NEEDS_REVIEW,
        )
        .order_by(Referral.created_at.desc())
        .limit(min(limit, 200))
    )
    return list(db.execute(stmt).scalars().all())


def apply_review(
    db: Session,
    *,
    referral: Referral,
    corrections: dict[str, str | None],
    reviewer_id: str,
    rerun_workflow: bool = True,
) -> dict:
    """Apply reviewer corrections, re-validate, audit, and optionally re-run.

    Only fields present in ``corrections`` that differ from the stored value are
    treated as changes. Human-corrected fields are assigned full confidence.
    """
    extracted = referral.extracted_data
    if extracted is None:
        raise ValueError("Referral has no extracted data to review")

    prior = {f: getattr(extracted, f) for f in EXTRACTION_FIELDS}
    merged = dict(prior)
    changed: dict[str, dict] = {}
    for field, value in corrections.items():
        if field in EXTRACTION_FIELDS and value is not None and value != prior.get(field):
            merged[field] = value
            changed[field] = {"from": prior.get(field), "to": value}

    prior_conf = extracted.field_confidence or {}
    confidence = {
        f: (1.0 if f in changed else float(prior_conf.get(f, 0.0))) for f in EXTRACTION_FIELDS
    }
    result = ExtractionResult(
        fields=merged, field_confidence=confidence, extractor="human_review"
    )

    report = validate(
        result,
        db=db,
        organization_id=referral.organization_id,
        exclude_referral_id=referral.id,
    )

    # Persist corrected data.
    for field in EXTRACTION_FIELDS:
        setattr(extracted, field, merged[field])
    extracted.field_confidence = confidence
    extracted.overall_confidence = result.overall_confidence
    extracted.extractor = "human_review"
    extracted.validation_status = report.status
    extracted.validation_report = report.as_dict()
    referral.patient_name = merged.get("patient_name")
    referral.referring_doctor = merged.get("referring_doctor")

    passed = report.status != ValidationStatus.FAILED
    referral.status = (
        ReferralStatus.VALIDATED if passed else ReferralStatus.NEEDS_REVIEW
    )

    audit.record(
        db,
        action="referral.reviewed",
        actor=reviewer_id,
        organization_id=referral.organization_id,
        referral_id=referral.id,
        entity_type="extracted_data",
        entity_id=extracted.id,
        detail={
            "changed_fields": list(changed.keys()),
            "changes": changed,
            "validation_status": report.status.value,
            "rerun_workflow": rerun_workflow and passed,
        },
    )

    execution_ids: list[str] = []
    if rerun_workflow and passed:
        execution_ids = workflow_engine.trigger(
            db,
            event="referral.received",
            organization_id=referral.organization_id,
            referral_id=referral.id,
            context={
                "extracted": merged,
                "validation": report.as_dict(),
                "overall_confidence": result.overall_confidence,
                "reviewed_by": reviewer_id,
            },
        )

    db.commit()

    if execution_ids:
        from app.workers.tasks import run_workflow_execution

        for execution_id in execution_ids:
            run_workflow_execution.delay(execution_id)

    return {
        "referral_id": referral.id,
        "status": referral.status.value,
        "validation_status": report.status.value,
        "changed_fields": list(changed.keys()),
        "workflow_executions": execution_ids,
    }
