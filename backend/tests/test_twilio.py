"""Twilio SMS adapter + notification dispatch tests (HTTP fully mocked)."""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services.providers import ProviderError, twilio_sms


def _configure_twilio(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC_test_sid", raising=False)
    monkeypatch.setattr(settings, "twilio_auth_token", "test_token", raising=False)
    monkeypatch.setattr(settings, "twilio_from_number", "+14155552671", raising=False)
    monkeypatch.setattr(settings, "twilio_messaging_service_sid", None, raising=False)


def _fake_post(status_code: int, payload: dict):
    def _post(url, data=None, auth=None, timeout=None):
        return httpx.Response(
            status_code, json=payload, request=httpx.Request("POST", url)
        )

    return _post


def test_send_success(monkeypatch):
    _configure_twilio(monkeypatch)
    monkeypatch.setattr(
        httpx, "post", _fake_post(201, {"sid": "SM123", "status": "queued"})
    )
    result = twilio_sms.send("+14155551234", "Your appointment is booked")
    assert result.success is True
    assert result.external_id == "SM123"
    assert result.status == "queued"


def test_invalid_recipient_skips_http(monkeypatch):
    _configure_twilio(monkeypatch)

    def _boom(*args, **kwargs):  # must never be called
        raise AssertionError("HTTP should not be attempted for bad E.164")

    monkeypatch.setattr(httpx, "post", _boom)
    result = twilio_sms.send("5551234", "hi")  # not E.164
    assert result.success is False
    assert result.status == "invalid_recipient"


def test_permanent_error_returns_failure(monkeypatch):
    _configure_twilio(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        _fake_post(400, {"code": 21211, "message": "Invalid 'To' Phone Number"}),
    )
    result = twilio_sms.send("+19999999999", "hi")
    assert result.success is False
    assert "21211" in result.error


def test_transient_error_raises_retryable(monkeypatch):
    _configure_twilio(monkeypatch)
    monkeypatch.setattr(httpx, "post", _fake_post(503, {"message": "service unavailable"}))
    with pytest.raises(ProviderError) as exc:
        twilio_sms.send("+14155551234", "hi")
    assert exc.value.retryable is True


def test_notification_mock_when_unconfigured(client, monkeypatch):
    """notification.send falls back to the mock when Twilio is not configured."""
    monkeypatch.setattr(settings, "twilio_account_sid", None, raising=False)
    from app.core.database import SessionLocal
    from app.services import notification

    db = SessionLocal()
    try:
        note = notification.send(
            db, channel="sms", recipient="+14155551234", body="hello"
        )
        assert note.sent is True
        assert note.payload["provider"] == "mock"
    finally:
        db.rollback()
        db.close()


def test_notification_uses_twilio_when_configured(client, monkeypatch):
    _configure_twilio(monkeypatch)
    monkeypatch.setattr(
        httpx, "post", _fake_post(201, {"sid": "SM999", "status": "sent"})
    )
    from app.core.database import SessionLocal
    from app.services import notification

    db = SessionLocal()
    try:
        note = notification.send(
            db, channel="sms", recipient="+14155551234", body="appt reminder"
        )
        assert note.sent is True
        assert note.payload["provider"] == "twilio"
        assert note.payload["external_id"] == "SM999"
    finally:
        db.rollback()
        db.close()
