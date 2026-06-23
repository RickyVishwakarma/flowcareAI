"""Referral processing pipeline: OCR → AI extraction → validation → trigger.

This is the vertical slice that ties the core modules together. It runs inside a
Celery task (app/workers/tasks.py) but is a plain function so it can be called
synchronously in tests or a no-broker dev setup.
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import ocr_confidence, referral_processing_seconds
from app.models.base import ReferralStatus, ValidationStatus
from app.models.referral import ExtractedData, Referral
from app.services import audit, extraction, ocr, storage, validation, workflow_engine

logger = get_logger(__name__)


def process_referral(db: Session, referral_id: str) -> dict:
    """Run the full extraction + validation pipeline for one referral."""
    started = time.perf_counter()
    referral = db.get(Referral, referral_id)
    if referral is None:
        raise ValueError(f"Referral {referral_id} not found")

    referral.status = ReferralStatus.PROCESSING
    db.flush()

    document = referral.documents[0] if referral.documents else None
    if document is None:
        referral.status = ReferralStatus.FAILED
        db.flush()
        raise ValueError("Referral has no document to process")

    # 1) OCR
    content = storage.load(document.storage_key)
    ocr_result = ocr.run_ocr(content, document.content_type, document.filename)
    document.ocr_text = ocr_result.text
    document.ocr_confidence = ocr_result.confidence
    ocr_confidence.observe(ocr_result.confidence)
    db.flush()
    audit.record(
        db,
        action="referral.parsed",
        organization_id=referral.organization_id,
        referral_id=referral.id,
        entity_type="referral_document",
        entity_id=document.id,
        detail={"backend": ocr_result.backend, "confidence": ocr_result.confidence},
    )

    # 2) AI extraction
    extraction_result = extraction.extract(ocr_result.text)
    referral.status = ReferralStatus.EXTRACTED

    # 3) Validation
    report = validation.validate(
        extraction_result,
        db=db,
        organization_id=referral.organization_id,
        exclude_referral_id=referral.id,
    )

    # 4) Persist structured data
    extracted = referral.extracted_data or ExtractedData(referral_id=referral.id)
    fields = extraction_result.fields
    extracted.patient_name = fields.get("patient_name")
    extracted.dob = fields.get("dob")
    extracted.insurance_provider = fields.get("insurance_provider")
    extracted.insurance_member_id = fields.get("insurance_member_id")
    extracted.referring_doctor = fields.get("referring_doctor")
    extracted.diagnosis = fields.get("diagnosis")
    extracted.referral_reason = fields.get("referral_reason")
    extracted.field_confidence = extraction_result.field_confidence
    extracted.overall_confidence = extraction_result.overall_confidence
    extracted.extractor = extraction_result.extractor
    extracted.validation_status = report.status
    extracted.validation_report = report.as_dict()
    if referral.extracted_data is None:
        db.add(extracted)

    # Denormalize a couple of fields for list views.
    referral.patient_name = extracted.patient_name
    referral.referring_doctor = extracted.referring_doctor

    referral.status = (
        ReferralStatus.NEEDS_REVIEW
        if report.status == ValidationStatus.FAILED
        else ReferralStatus.VALIDATED
    )
    db.flush()
    audit.record(
        db,
        action="referral.extracted",
        organization_id=referral.organization_id,
        referral_id=referral.id,
        entity_type="extracted_data",
        entity_id=extracted.id,
        detail={
            "extractor": extraction_result.extractor,
            "overall_confidence": extraction_result.overall_confidence,
            "validation_status": report.status.value,
        },
    )

    # 5) Fire the workflow trigger.
    execution_ids = workflow_engine.trigger(
        db,
        event="referral.received",
        organization_id=referral.organization_id,
        referral_id=referral.id,
        context={
            "extracted": fields,
            "validation": report.as_dict(),
            "overall_confidence": extraction_result.overall_confidence,
        },
    )

    db.commit()
    referral_processing_seconds.observe(time.perf_counter() - started)

    # Dispatch each created execution to the queue (async) or run inline.
    from app.workers.tasks import run_workflow_execution

    for execution_id in execution_ids:
        run_workflow_execution.delay(execution_id)

    return {
        "referral_id": referral.id,
        "status": referral.status.value,
        "extractor": extraction_result.extractor,
        "validation_status": report.status.value,
        "workflow_executions": execution_ids,
    }
