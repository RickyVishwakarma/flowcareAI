"""Provider matching + referral-leakage detection.

Given a referral, infer the needed specialty, then rank the organization's
providers by specialty fit, insurance acceptance, in-network status, and
availability. Flags **leakage risk** when no in-network provider can serve the
patient (specialty + insurance) — i.e., the patient would be referred outside
the network, which is lost revenue for a health system.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider import Provider, ProviderMatch
from app.models.referral import Referral

# Keyword → specialty. Inference is intentionally simple/deterministic; an LLM
# classifier could replace it behind the same interface.
SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "cardiology": ["cardio", "heart", "chest pain", "hypertension", "ekg", "arrhythmia"],
    "neurology": ["neuro", "migraine", "headache", "seizure", "stroke", "epilep"],
    "orthopedics": ["ortho", "knee", "joint", "fracture", "bone", "back pain", "shoulder"],
    "endocrinology": ["diabet", "thyroid", "endocrin", "hormone", "insulin"],
    "pulmonology": ["pulmon", "copd", "asthma", "lung", "respiratory", "breath"],
    "gastroenterology": ["gastro", "stomach", "colon", "liver", "ibs", "reflux"],
    "dermatology": ["derm", "skin", "rash", "lesion", "acne"],
}

# Scoring weights.
W_SPECIALTY = 50
W_INSURANCE = 40
W_IN_NETWORK = 30
W_AVAILABILITY = 20  # scaled by wait time


def infer_specialty(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        if any(k in blob for k in keywords):
            return specialty
    return None


def _accepts(provider: Provider, insurance: str | None) -> bool:
    if not insurance:
        return False
    accepted = [i.lower() for i in (provider.accepted_insurances or [])]
    return insurance.lower() in accepted


def _score(provider: Provider, specialty: str | None, insurance: str | None) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if specialty and provider.specialty.lower() == specialty:
        score += W_SPECIALTY
        reasons.append("specialty match")
    if _accepts(provider, insurance):
        score += W_INSURANCE
        reasons.append("accepts insurance")
    if provider.in_network:
        score += W_IN_NETWORK
        reasons.append("in-network")
    # Sooner availability scores higher (0 wait → full points).
    avail = max(0.0, W_AVAILABILITY - provider.current_wait_days)
    score += avail
    if provider.current_wait_days <= 7:
        reasons.append(f"{provider.current_wait_days}d wait")
    return round(score, 1), reasons


def match(db: Session, referral: Referral) -> dict:
    """Rank providers for a referral and detect leakage. Pure computation."""
    extracted = referral.extracted_data
    insurance = extracted.insurance_provider if extracted else None
    specialty = infer_specialty(
        extracted.referral_reason if extracted else None,
        extracted.diagnosis if extracted else None,
    )

    providers = db.execute(
        select(Provider).where(
            Provider.organization_id == referral.organization_id,
            Provider.is_active.is_(True),
        )
    ).scalars().all()

    # Candidate pool: providers in the needed specialty (or all if unknown).
    pool = [p for p in providers if specialty is None or p.specialty.lower() == specialty]

    scored = []
    for p in pool:
        s, reasons = _score(p, specialty, insurance)
        scored.append(
            {
                "provider_id": p.id,
                "name": p.name,
                "specialty": p.specialty,
                "in_network": p.in_network,
                "accepts_insurance": _accepts(p, insurance),
                "wait_days": p.current_wait_days,
                "score": s,
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda c: c["score"], reverse=True)

    in_network_viable = [
        c for c in scored if c["in_network"] and c["accepts_insurance"]
    ]
    chosen = scored[0] if scored else None
    leakage_risk = len(in_network_viable) == 0

    return {
        "specialty": specialty,
        "insurance": insurance,
        "chosen": chosen,
        "in_network": bool(chosen and chosen["in_network"]),
        "accepts_insurance": bool(chosen and chosen["accepts_insurance"]),
        "leakage_risk": leakage_risk,
        "score": chosen["score"] if chosen else 0.0,
        "candidates": scored,
    }


def run_and_store(db: Session, referral: Referral) -> ProviderMatch:
    """Run the matcher and persist a ProviderMatch record."""
    result = match(db, referral)
    chosen = result["chosen"]
    record = ProviderMatch(
        referral_id=referral.id,
        provider_id=chosen["provider_id"] if chosen else None,
        specialty=result["specialty"],
        in_network=result["in_network"],
        accepts_insurance=result["accepts_insurance"],
        leakage_risk=result["leakage_risk"],
        score=result["score"],
        candidates=result["candidates"],
    )
    db.add(record)
    db.flush()
    return record
