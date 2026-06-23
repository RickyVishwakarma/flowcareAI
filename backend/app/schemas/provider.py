"""Provider + matching schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    specialty: str
    accepted_insurances: list[str] = []
    location: str | None = None
    in_network: bool = True
    weekly_capacity: int = 20
    current_wait_days: int = 7


class ProviderOut(ProviderCreate):
    id: str
    is_active: bool

    model_config = {"from_attributes": True}


class MatchRequest(BaseModel):
    referral_id: str


class Candidate(BaseModel):
    provider_id: str
    name: str
    specialty: str
    in_network: bool
    accepts_insurance: bool
    wait_days: int
    score: float
    reasons: list[str]


class MatchResult(BaseModel):
    referral_id: str
    specialty: str | None
    insurance: str | None
    leakage_risk: bool
    in_network: bool
    accepts_insurance: bool
    score: float
    chosen: Candidate | None
    candidates: list[Candidate]
