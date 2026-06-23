"""Audit logging — append-only, immutable event trail."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.operations import AuditLog


def record(
    db: Session,
    *,
    action: str,
    actor: str = "system",
    organization_id: str | None = None,
    referral_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> AuditLog:
    """Insert an audit row. Never updated or deleted by application code."""
    entry = AuditLog(
        action=action,
        actor=actor,
        organization_id=organization_id,
        referral_id=referral_id,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
    )
    db.add(entry)
    db.flush()
    return entry
