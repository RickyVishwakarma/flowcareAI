"""Notification service — email / SMS / webhook / in-app.

SMS dispatches through the real Twilio adapter when credentials are configured
(``settings.has_twilio``); otherwise it falls back to a logged mock so the
pipeline runs without external dependencies. Email/webhook remain mock senders
(SES / httpx adapters are the next integration milestone).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.base import NotificationChannel
from app.models.operations import Notification
from app.services.providers import ProviderResult
from app.services.providers import twilio_sms

logger = get_logger(__name__)


def send(
    db: Session,
    *,
    channel: NotificationChannel | str,
    recipient: str,
    subject: str | None = None,
    body: str | None = None,
    referral_id: str | None = None,
    payload: dict | None = None,
) -> Notification:
    if isinstance(channel, str):
        channel = NotificationChannel(channel)

    notification = Notification(
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        referral_id=referral_id,
        payload=payload or {},
    )

    if channel == NotificationChannel.SMS:
        _dispatch_sms(notification)
    else:
        # Mock dispatch — swap for SES / webhook adapters in production.
        logger.info("Dispatching %s notification to %s: %s", channel.value, recipient, subject)
        notification.sent = True

    db.add(notification)
    db.flush()
    return notification


def _dispatch_sms(notification: Notification) -> None:
    """Send via Twilio when configured. May raise ProviderError (retryable) which
    the task layer translates into retry → backoff → DLQ."""
    if not settings.has_twilio:
        logger.info("Twilio not configured; mock SMS to %s", notification.recipient)
        notification.sent = True
        notification.payload = {**notification.payload, "provider": "mock"}
        return

    result: ProviderResult = twilio_sms.send(notification.recipient, notification.body or "")
    notification.sent = result.success
    notification.payload = {
        **notification.payload,
        "provider": result.provider,
        "external_id": result.external_id,
        "status": result.status,
        "error": result.error,
    }
    if result.success:
        logger.info(
            "Twilio SMS accepted: sid=%s status=%s", result.external_id, result.status
        )
    else:
        logger.warning("Twilio SMS not delivered: %s", result.error)
