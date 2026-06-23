"""Provider directory + referral→provider match records."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Provider(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "providers"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    specialty: Mapped[str] = mapped_column(String(64), index=True)
    accepted_insurances: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[str | None] = mapped_column(String(255))
    in_network: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_capacity: Mapped[int] = mapped_column(Integer, default=20)
    current_wait_days: Mapped[int] = mapped_column(Integer, default=7)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderMatch(UUIDMixin, TimestampMixin, Base):
    """One row per match run for a referral (history, like insurance_verifications)."""

    __tablename__ = "provider_matches"

    referral_id: Mapped[str] = mapped_column(
        ForeignKey("referrals.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[str | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL")
    )
    specialty: Mapped[str | None] = mapped_column(String(64))
    in_network: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_insurance: Mapped[bool] = mapped_column(Boolean, default=False)
    leakage_risk: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
