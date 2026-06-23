"""Insurance verification service.

Mocks an external payer eligibility API (e.g. Availity / Change Healthcare).
Deterministic by member id so demos are repeatable. Stores verification history.
"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.models.base import InsuranceStatus
from app.models.operations import InsuranceVerification


def verify(
    db: Session,
    *,
    referral_id: str,
    provider: str | None,
    member_id: str | None,
) -> InsuranceVerification:
    """Call the (mock) payer API and persist a verification record."""
    result = _mock_payer_call(provider, member_id)
    record = InsuranceVerification(
        referral_id=referral_id,
        provider=provider,
        member_id=member_id,
        status=result["status"],
        coverage_active=result["coverage_active"],
        eligibility=result["eligibility"],
        raw_response=result,
    )
    db.add(record)
    db.flush()

    if not result["coverage_active"]:
        from app.core.metrics import insurance_verification_failures

        insurance_verification_failures.labels(reason=result["status"].value).inc()
    return record


def _mock_payer_call(provider: str | None, member_id: str | None) -> dict:
    """Deterministic pseudo-eligibility based on a hash of the member id."""
    if not member_id:
        return {
            "status": InsuranceStatus.UNKNOWN,
            "coverage_active": False,
            "eligibility": {},
            "reason": "missing_member_id",
        }
    digest = int(hashlib.sha256(member_id.encode()).hexdigest(), 16)
    active = digest % 10 != 0  # ~90% active
    return {
        "status": InsuranceStatus.ACTIVE if active else InsuranceStatus.INACTIVE,
        "coverage_active": active,
        "eligibility": {
            "plan": "PPO" if digest % 2 else "HMO",
            "copay_usd": 20 + (digest % 5) * 10,
            "deductible_remaining_usd": (digest % 2000),
            "policy_status": "active" if active else "terminated",
        },
        "provider": provider,
    }
