"""Dashboard response schema."""
from __future__ import annotations

from pydantic import BaseModel


class TimePoint(BaseModel):
    date: str
    count: int


class DashboardStats(BaseModel):
    referrals_total: int
    referrals_by_status: dict[str, int]
    referrals_by_source: dict[str, int]
    referrals_timeseries: list[TimePoint]
    validation_breakdown: dict[str, int]
    extractor_breakdown: dict[str, int]
    avg_confidence: float | None
    workflow_total: int
    workflow_by_status: dict[str, int]
    workflow_success_rate: float
    insurance_total: int
    insurance_active: int
    insurance_active_rate: float
    appointments_total: int
    review_queue_size: int
    open_tasks: int
