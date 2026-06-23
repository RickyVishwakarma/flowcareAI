"""Appointment scheduling engine (mock provider availability)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.base import AppointmentStatus
from app.models.operations import Appointment

_BUSINESS_START_HOUR = 9
_SLOT_MINUTES = 30


def next_available_slot(after: datetime | None = None) -> datetime:
    """Return the next business-hours slot (mock availability)."""
    base = after or datetime.now(timezone.utc)
    candidate = base.replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    candidate = candidate.replace(hour=_BUSINESS_START_HOUR)
    # Skip weekends.
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def schedule(
    db: Session,
    *,
    referral_id: str,
    provider_name: str | None = None,
    when: datetime | None = None,
    duration_minutes: int = _SLOT_MINUTES,
) -> Appointment:
    appt = Appointment(
        referral_id=referral_id,
        provider_name=provider_name or "Auto-assigned Provider",
        scheduled_for=when or next_available_slot(),
        duration_minutes=duration_minutes,
        status=AppointmentStatus.SCHEDULED,
        location="Telehealth",
    )
    db.add(appt)
    db.flush()
    return appt


def reschedule(db: Session, appointment: Appointment, when: datetime) -> Appointment:
    appointment.scheduled_for = when
    appointment.status = AppointmentStatus.RESCHEDULED
    db.flush()
    return appointment


def cancel(db: Session, appointment: Appointment) -> Appointment:
    appointment.status = AppointmentStatus.CANCELLED
    db.flush()
    return appointment
