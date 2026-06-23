"""Password hashing and JWT token helpers."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"
VERIFY = "verify"
EMAIL_TOKEN_EXPIRE_HOURS = 24

# bcrypt only hashes the first 72 bytes; truncate explicitly to avoid a
# ValueError on longer inputs with bcrypt >= 4.1.
_MAX_BCRYPT_BYTES = 72


def _to_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def new_jti() -> str:
    return str(uuid.uuid4())


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    jti: str | None = None,
    **claims: Any,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": jti or new_jti(),
        **claims,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject,
        ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
        **claims,
    )


def create_refresh_token(subject: str, jti: str | None = None, **claims: Any) -> str:
    return _create_token(
        subject,
        REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
        jti=jti,
        **claims,
    )


def create_email_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject, VERIFY, timedelta(hours=EMAIL_TOKEN_EXPIRE_HOURS), **claims
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
