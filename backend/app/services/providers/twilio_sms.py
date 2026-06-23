"""Twilio SMS adapter — real REST integration against the Twilio Messages API.

Implements the documented contract:
    POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
    Auth:  HTTP Basic (Account SID : Auth Token)
    Body:  form-encoded  To, Body, and either From or MessagingServiceSid
    201 →  {"sid": "SM…", "status": "queued", ...}
    4xx →  {"code": 21211, "message": "Invalid 'To' Phone Number", ...}

Error handling mirrors Twilio's semantics:
  * 2xx                      → success
  * 429 / 5xx / network      → ProviderError(retryable=True)  (task layer retries)
  * other 4xx (bad number…)  → non-success ProviderResult     (do not retry)
"""
from __future__ import annotations

import re

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.providers import ProviderError, ProviderResult

logger = get_logger(__name__)

# Twilio statuses that mean "accepted for delivery".
_ACCEPTED = {"accepted", "queued", "sending", "sent", "delivered"}
_E164 = re.compile(r"^\+[1-9]\d{1,14}$")


def is_e164(number: str) -> bool:
    return bool(_E164.match(number or ""))


def send(to: str, body: str) -> ProviderResult:
    """Send an SMS via Twilio. Assumes settings.has_twilio is True."""
    if not is_e164(to):
        return ProviderResult(
            success=False,
            provider="twilio",
            status="invalid_recipient",
            error=f"'{to}' is not a valid E.164 phone number",
        )

    url = (
        f"{settings.twilio_base_url}/2010-04-01/Accounts/"
        f"{settings.twilio_account_sid}/Messages.json"
    )
    form: dict[str, str] = {"To": to, "Body": body}
    if settings.twilio_messaging_service_sid:
        form["MessagingServiceSid"] = settings.twilio_messaging_service_sid
    else:
        form["From"] = settings.twilio_from_number  # type: ignore[assignment]

    try:
        response = httpx.post(
            url,
            data=form,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=settings.twilio_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ProviderError(f"Twilio request failed: {exc}", retryable=True) from exc

    return _interpret(response)


def _interpret(response: httpx.Response) -> ProviderResult:
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.is_success:
        status = payload.get("status", "queued")
        return ProviderResult(
            success=status in _ACCEPTED,
            provider="twilio",
            external_id=payload.get("sid"),
            status=status,
            raw=payload,
        )

    message = payload.get("message", response.text[:200])
    if response.status_code == 429 or response.status_code >= 500:
        # Rate limited or Twilio-side error → let the task layer retry.
        raise ProviderError(
            f"Twilio transient error {response.status_code}: {message}", retryable=True
        )

    # Permanent client error (e.g. invalid number, unverified sender).
    logger.warning("Twilio permanent error %s: %s", response.status_code, message)
    return ProviderResult(
        success=False,
        provider="twilio",
        status="failed",
        error=f"{payload.get('code', response.status_code)}: {message}",
        raw=payload,
    )
