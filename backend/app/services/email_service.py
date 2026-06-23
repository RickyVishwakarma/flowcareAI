"""Transactional email (verification, etc.).

Mock sender for now — logs the message and returns the link so dev/non-prod
callers can complete the flow without an email provider. Swap `_deliver` for an
SES / SMTP adapter (the same ProviderResult shape as Twilio) in production.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _frontend_base() -> str:
    # Best-effort; the link path is what matters for the SPA route.
    return "http://localhost:3000"


def send_verification_email(email: str, token: str) -> str:
    """'Send' an email-verification link. Returns the link (for dev convenience)."""
    link = f"{_frontend_base()}/verify-email?token={token}"
    _deliver(
        to=email,
        subject="Verify your FlowCare AI email",
        body=f"Confirm your email by visiting: {link}",
    )
    return link


def _deliver(*, to: str, subject: str, body: str) -> None:
    # Mock delivery. The link is logged so it can be used without a real inbox.
    logger.info("[MOCK EMAIL] to=%s subject=%r | %s", to, subject, body)


def expose_link_in_response() -> bool:
    """In non-production we return the verification link in the API response so
    the flow is testable without an inbox. Never do this in production."""
    return not settings.is_production
