"""Validation engine.

Validates extracted referral data: required fields, date formats, insurance
completeness, confidence thresholds, and duplicate detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import ValidationStatus
from app.models.referral import ExtractedData
from app.services.extraction import ExtractionResult

REQUIRED_FIELDS = ["patient_name", "dob", "insurance_provider"]
INSURANCE_FIELDS = ["insurance_provider", "insurance_member_id"]
LOW_CONFIDENCE = 0.5

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOOSE_DATE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")


@dataclass
class ValidationReport:
    status: ValidationStatus
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "status": self.status.value,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
        }


def validate(
    result: ExtractionResult,
    db: Session | None = None,
    organization_id: str | None = None,
    exclude_referral_id: str | None = None,
) -> ValidationReport:
    report = ValidationReport(status=ValidationStatus.PASSED)
    fields = result.fields

    # Required fields present.
    for name in REQUIRED_FIELDS:
        present = bool(fields.get(name))
        report.checks[f"required:{name}"] = present
        if not present:
            report.errors.append(f"Missing required field: {name}")

    # Date format.
    dob = fields.get("dob")
    if dob:
        ok = bool(_ISO_DATE.match(dob) or _LOOSE_DATE.match(dob))
        report.checks["dob_format"] = ok
        if not ok:
            report.warnings.append(f"DOB '{dob}' is not a recognized date format")

    # Insurance completeness.
    missing_ins = [f for f in INSURANCE_FIELDS if not fields.get(f)]
    report.checks["insurance_complete"] = not missing_ins
    if missing_ins:
        report.warnings.append(f"Incomplete insurance info: missing {', '.join(missing_ins)}")

    # Low-confidence fields.
    for name, conf in result.field_confidence.items():
        if fields.get(name) and conf < LOW_CONFIDENCE:
            report.warnings.append(f"Low confidence ({conf:.2f}) on field: {name}")

    # Duplicate detection (same patient + dob in the org).
    if db is not None and organization_id and fields.get("patient_name") and fields.get("dob"):
        if _is_duplicate(db, organization_id, fields, exclude_referral_id):
            report.checks["duplicate"] = True
            report.warnings.append("Possible duplicate referral for this patient + DOB")
        else:
            report.checks["duplicate"] = False

    # Terminal status.
    if report.errors:
        report.status = ValidationStatus.FAILED
    elif report.warnings:
        report.status = ValidationStatus.PASSED_WITH_WARNINGS
    return report


def _is_duplicate(
    db: Session,
    organization_id: str,
    fields: dict,
    exclude_referral_id: str | None,
) -> bool:
    from app.models.referral import Referral

    stmt = (
        select(ExtractedData)
        .join(Referral, Referral.id == ExtractedData.referral_id)
        .where(
            Referral.organization_id == organization_id,
            ExtractedData.patient_name == fields["patient_name"],
            ExtractedData.dob == fields["dob"],
        )
    )
    if exclude_referral_id:
        stmt = stmt.where(ExtractedData.referral_id != exclude_referral_id)
    return db.execute(stmt).first() is not None
