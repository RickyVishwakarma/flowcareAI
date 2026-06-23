"""Referral schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.base import ReferralSource, ReferralStatus


class ReferralFormSubmission(BaseModel):
    """Structured web-form intake (alternative to file upload)."""

    patient_name: str
    dob: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    referring_doctor: str | None = None
    diagnosis: str | None = None
    referral_reason: str | None = None


class ExtractedDataOut(BaseModel):
    patient_name: str | None = None
    dob: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    referring_doctor: str | None = None
    diagnosis: str | None = None
    referral_reason: str | None = None
    field_confidence: dict = {}
    overall_confidence: float | None = None
    extractor: str | None = None
    validation_status: str | None = None
    validation_report: dict = {}

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str | None
    size_bytes: int
    ocr_confidence: float | None

    model_config = {"from_attributes": True}


class ReferralOut(BaseModel):
    id: str
    reference_code: str
    source: ReferralSource
    status: ReferralStatus
    patient_name: str | None
    referring_doctor: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralDetail(ReferralOut):
    documents: list[DocumentOut] = []
    extracted_data: ExtractedDataOut | None = None


class ReferralAccepted(BaseModel):
    id: str
    reference_code: str
    status: ReferralStatus
    task_id: str | None = None
