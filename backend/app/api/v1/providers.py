"""Provider directory + referral→provider matching / leakage detection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.base import UserRole
from app.models.organization import User
from app.models.provider import Provider, ProviderMatch
from app.models.referral import Referral
from app.schemas.provider import MatchRequest, MatchResult, ProviderCreate, ProviderOut
from app.services import audit, matching

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
def list_providers(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Provider]:
    stmt = (
        select(Provider)
        .where(Provider.organization_id == user.organization_id)
        .order_by(Provider.specialty, Provider.name)
    )
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.AGENT)),
) -> Provider:
    provider = Provider(organization_id=user.organization_id, **payload.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _owned_referral(db: Session, referral_id: str, user: User) -> Referral:
    referral = db.get(Referral, referral_id)
    if referral is None or referral.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral


@router.post("/match", response_model=MatchResult)
def run_match(
    payload: MatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MatchResult:
    referral = _owned_referral(db, payload.referral_id, user)
    record = matching.run_and_store(db, referral)
    audit.record(
        db,
        action="provider.matched",
        actor=user.id,
        organization_id=user.organization_id,
        referral_id=referral.id,
        entity_type="provider_match",
        entity_id=record.id,
        detail={
            "specialty": record.specialty,
            "provider_id": record.provider_id,
            "leakage_risk": record.leakage_risk,
        },
    )
    db.commit()
    return _to_result(referral.id, record)


@router.get("/match/{referral_id}", response_model=MatchResult | None)
def latest_match(
    referral_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MatchResult | None:
    _owned_referral(db, referral_id, user)
    record = db.execute(
        select(ProviderMatch)
        .where(ProviderMatch.referral_id == referral_id)
        .order_by(ProviderMatch.created_at.desc())
    ).scalars().first()
    return _to_result(referral_id, record) if record else None


def _to_result(referral_id: str, record: ProviderMatch) -> MatchResult:
    candidates = record.candidates or []
    chosen = next((c for c in candidates if c["provider_id"] == record.provider_id), None)
    return MatchResult(
        referral_id=referral_id,
        specialty=record.specialty,
        insurance=None,
        leakage_risk=record.leakage_risk,
        in_network=record.in_network,
        accepts_insurance=record.accepts_insurance,
        score=record.score,
        chosen=chosen,
        candidates=candidates,
    )
