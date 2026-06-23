"""Review-queue schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewQueueItem(BaseModel):
    id: str
    reference_code: str
    status: str
    patient_name: str | None
    created_at: datetime
    error_count: int
    warning_count: int


class ReviewDetail(BaseModel):
    id: str
    reference_code: str
    status: str
    ocr_text: str | None
    fields: dict[str, str | None]
    field_confidence: dict
    validation_report: dict


class ReviewSubmission(BaseModel):
    """Corrected field values. Omitted/null fields keep their current value."""

    patient_name: str | None = None
    dob: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    referring_doctor: str | None = None
    diagnosis: str | None = None
    referral_reason: str | None = None
    rerun_workflow: bool = True


class ReviewResult(BaseModel):
    referral_id: str
    status: str
    validation_status: str
    changed_fields: list[str]
    workflow_executions: list[str]
