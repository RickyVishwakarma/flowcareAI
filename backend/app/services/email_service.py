"""Transactional email (verification, password reset).

Sends via real SMTP when configured (`settings.has_smtp`); otherwise logs the
message and returns the link so dev/non-prod callers can complete the flow
without an email provider. Works with Gmail (app password), Mailtrap, SendGrid,
SES SMTP — anything speaking SMTP.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _link(path: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}{path}"


def send_verification_email(email: str, token: str) -> str:
    link = _link(f"/verify-email?token={token}")
    _deliver(
        to=email,
        subject="Verify your FlowCare AI email",
        body=f"Welcome to FlowCare AI!\n\nConfirm your email address:\n{link}\n\n"
        "This link expires in 24 hours.",
    )
    return link


def send_password_reset_email(email: str, token: str) -> str:
    link = _link(f"/reset-password?token={token}")
    _deliver(
        to=email,
        subject="Reset your FlowCare AI password",
        body=f"We received a request to reset your password.\n\nReset it here:\n{link}\n\n"
        "This link expires in 1 hour. If you didn't request this, ignore this email.",
    )
    return link


def _deliver(*, to: str, subject: str, body: str) -> None:
    if not settings.has_smtp:
        logger.info("[MOCK EMAIL] to=%s subject=%r | %s", to, subject, body.replace("\n", " "))
        return
    try:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Sent email to %s: %s", to, subject)
    except Exception as exc:  # noqa: BLE001 — don't fail the request on email trouble
        logger.warning("SMTP send failed (%s); email not delivered to %s", exc, to)


def expose_link_in_response() -> bool:
    """In non-production we return the link in the API response so flows are
    testable without an inbox. Never do this in production."""
    return not settings.is_production
