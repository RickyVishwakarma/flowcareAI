"""Authentication service: sessions, refresh rotation, reuse detection, lockout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    new_jti,
    verify_password,
)
from app.models.auth import RefreshSession
from app.models.organization import User

logger = get_logger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class AuthError(Exception):
    """Raised for authentication failures (mapped to 401/423 in the router)."""

    def __init__(self, message: str, *, locked: bool = False) -> None:
        super().__init__(message)
        self.locked = locked


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Coerce a possibly naive datetime (SQLite) to UTC-aware for comparison."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _access_claims(user: User) -> dict:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return {"org": user.organization_id, "role": role}


def _issue(db: Session, user: User, *, family_id: str, request_meta: dict | None = None) -> tuple[str, str]:
    """Create an access token + a tracked refresh token in the given family."""
    jti = new_jti()
    access = create_access_token(user.id, **_access_claims(user))
    refresh = create_refresh_token(user.id, jti=jti, fam=family_id)
    session = RefreshSession(
        user_id=user.id,
        jti=jti,
        family_id=family_id,
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        user_agent=(request_meta or {}).get("user_agent"),
        ip_address=(request_meta or {}).get("ip"),
        last_used_at=_now(),
    )
    db.add(session)
    db.flush()
    return access, refresh


# ── Login ────────────────────────────────────────────────────────────


def authenticate(db: Session, email: str, password: str, request_meta: dict | None = None) -> tuple[User, str, str]:
    """Verify credentials with lockout, then start a new session family."""
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user and (locked := _aware(user.locked_until)) and locked > _now():
        raise AuthError("Account temporarily locked due to failed logins", locked=True)

    if user is None or not verify_password(password, user.hashed_password):
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
                logger.warning("User %s locked after repeated failures", email)
            db.commit()
        raise AuthError("Invalid email or password")

    if not user.is_active:
        raise AuthError("User account is disabled")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _now()

    access, refresh = _issue(db, user, family_id=new_jti(), request_meta=request_meta)
    db.commit()
    return user, access, refresh


# ── Refresh (rotation + reuse detection) ─────────────────────────────


def rotate(db: Session, refresh_token: str, request_meta: dict | None = None) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid refresh token") from exc
    if payload.get("type") != REFRESH:
        raise AuthError("Not a refresh token")

    jti = payload.get("jti")
    session = db.execute(
        select(RefreshSession).where(RefreshSession.jti == jti)
    ).scalar_one_or_none()
    if session is None:
        raise AuthError("Unknown refresh token")

    if session.revoked:
        # A revoked (already-rotated) token is being replayed → likely theft.
        # Revoke the entire family so neither party can continue.
        _revoke_family(db, session.family_id)
        db.commit()
        logger.warning("Refresh token reuse detected; revoked family %s", session.family_id)
        raise AuthError("Refresh token reuse detected; session revoked")

    if _aware(session.expires_at) <= _now():
        raise AuthError("Refresh token expired")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AuthError("User account is disabled")

    # Rotate: revoke current, issue a new one in the same family.
    access, refresh = _issue(db, user, family_id=session.family_id, request_meta=request_meta)
    new = db.execute(
        select(RefreshSession)
        .where(RefreshSession.family_id == session.family_id, RefreshSession.revoked == False)  # noqa: E712
        .order_by(RefreshSession.created_at.desc())
    ).scalars().first()
    session.revoked = True
    session.revoked_at = _now()
    session.replaced_by = new.jti if new else None
    db.commit()
    return access, refresh


# ── Revocation ───────────────────────────────────────────────────────


def revoke_by_token(db: Session, refresh_token: str) -> None:
    """Logout: revoke the session for a given refresh token (idempotent)."""
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        return
    jti = payload.get("jti")
    session = db.execute(
        select(RefreshSession).where(RefreshSession.jti == jti)
    ).scalar_one_or_none()
    if session and not session.revoked:
        session.revoked = True
        session.revoked_at = _now()
        db.commit()


def revoke_all_for_user(db: Session, user_id: str) -> int:
    result = db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked == False)  # noqa: E712
        .values(revoked=True, revoked_at=_now())
    )
    db.commit()
    return result.rowcount or 0


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.family_id == family_id, RefreshSession.revoked == False)  # noqa: E712
        .values(revoked=True, revoked_at=_now())
    )


def issue_fresh_session(db: Session, user: User, request_meta: dict | None = None) -> tuple[str, str]:
    """Start a brand-new session family (used after password change)."""
    access, refresh = _issue(db, user, family_id=new_jti(), request_meta=request_meta)
    db.commit()
    return access, refresh
