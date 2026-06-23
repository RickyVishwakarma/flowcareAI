"""Referral, document, and extracted-data models."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import (
    ReferralSource,
    ReferralStatus,
    TimestampMixin,
    UUIDMixin,
    ValidationStatus,
)


class Referral(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "referrals"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    reference_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    source: Mapped[ReferralSource] = mapped_column(String(32))
    status: Mapped[ReferralStatus] = mapped_column(
        String(32), default=ReferralStatus.RECEIVED, index=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    # Convenience denormalized fields, populated after extraction.
    patient_name: Mapped[str | None] = mapped_column(String(255))
    referring_doctor: Mapped[str | None] = mapped_column(String(255))

    documents: Mapped[list["ReferralDocument"]] = relationship(
        back_populates="referral", cascade="all, delete-orphan"
    )
    extracted_data: Mapped["ExtractedData | None"] = relationship(
        back_populates="referral", cascade="all, delete-orphan", uselist=False
    )


class ReferralDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "referral_documents"

    referral_id: Mapped[str] = mapped_column(
        ForeignKey("referrals.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)

    referral: Mapped["Referral"] = relationship(back_populates="documents")


class ExtractedData(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "extracted_data"

    referral_id: Mapped[str] = mapped_column(
        ForeignKey("referrals.id", ondelete="CASCADE"), unique=True, index=True
    )
    # Structured healthcare fields.
    patient_name: Mapped[str | None] = mapped_column(String(255))
    dob: Mapped[str | None] = mapped_column(String(32))
    insurance_provider: Mapped[str | None] = mapped_column(String(255))
    insurance_member_id: Mapped[str | None] = mapped_column(String(128))
    referring_doctor: Mapped[str | None] = mapped_column(String(255))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    referral_reason: Mapped[str | None] = mapped_column(Text)

    # Per-field confidence + provenance.
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    extractor: Mapped[str | None] = mapped_column(String(64))  # claude | template

    # Validation outcome.
    validation_status: Mapped[ValidationStatus | None] = mapped_column(String(32))
    validation_report: Mapped[dict] = mapped_column(JSON, default=dict)

    referral: Mapped["Referral"] = relationship(back_populates="extracted_data")
