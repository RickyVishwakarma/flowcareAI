"""Appointments, insurance verifications, notifications, tasks, audit logs."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import (
    AppointmentStatus,
    InsuranceStatus,
    NotificationChannel,
    TaskStatus,
    TimestampMixin,
    UUIDMixin,
)


class InsuranceVerification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "insurance_verifications"

    referral_id: Mapped[str] = mapped_column(
        ForeignKey("referrals.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str | None] = mapped_column(String(255))
    member_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[InsuranceStatus] = mapped_column(String(32), default=InsuranceStatus.UNKNOWN)
    coverage_active: Mapped[bool | None] = mapped_column(Boolean)
    eligibility: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)


class Appointment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "appointments"

    referral_id: Mapped[str] = mapped_column(
        ForeignKey("referrals.id", ondelete="CASCADE"), index=True
    )
    provider_name: Mapped[str | None] = mapped_column(String(255))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(default=30)
    status: Mapped[AppointmentStatus] = mapped_column(
        String(32), default=AppointmentStatus.SCHEDULED
    )
    location: Mapped[str | None] = mapped_column(String(512))
    notes: Mapped[str | None] = mapped_column(Text)


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    referral_id: Mapped[str | None] = mapped_column(
        ForeignKey("referrals.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(String(32))
    recipient: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str | None] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    referral_id: Mapped[str | None] = mapped_column(
        ForeignKey("referrals.id", ondelete="SET NULL"), index=True
    )
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(String(32), default=TaskStatus.OPEN, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """Append-only, immutable audit trail. No updates/deletes in app code."""

    __tablename__ = "audit_logs"

    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    referral_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor: Mapped[str | None] = mapped_column(String(255))  # user id or "system"
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
