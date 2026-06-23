"""Authentication: signup, login lockout, refresh rotation + reuse detection,
logout, and password change."""
from __future__ import annotations

import uuid


def _email() -> str:
    return f"user_{uuid.uuid4().hex[:8]}@clinic-demo.com"


def test_signup_creates_org_and_logs_in(client):
    email = _email()
    r = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Test Clinic", "email": email, "password": "supersecret1"},
    )
    assert r.status_code == 201, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    # The new user is an admin of their own org.
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["role"] == "admin"

    # Duplicate email is rejected.
    dup = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Another Clinic", "email": email, "password": "supersecret1"},
    )
    assert dup.status_code == 409


def test_email_verification_flow(client):
    email = _email()
    signup = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Verify Clinic", "email": email, "password": "verifyme123"},
    ).json()
    headers = {"Authorization": f"Bearer {signup['access_token']}"}

    # Dev returns the verification link so the flow is testable without an inbox.
    assert signup["verification_link"], signup
    token = signup["verification_link"].split("token=")[1]

    # /me carries the org name + unverified status (fixes the "UI shows nothing" gap).
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["organization_name"] == "Verify Clinic"
    assert me["email_verified"] is False

    # Verify, then /me flips to verified.
    v = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert v.status_code == 200
    me2 = client.get("/api/v1/auth/me", headers=headers).json()
    assert me2["email_verified"] is True

    # Bad token is rejected.
    assert client.post("/api/v1/auth/verify-email", json={"token": "garbage"}).status_code == 400


def test_password_reset_flow(client):
    email = _email()
    tokens = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Reset Clinic", "email": email, "password": "originalpw1"},
    ).json()

    # Forgot password → dev returns the reset link; response never reveals existence.
    fp = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert fp.status_code == 200
    assert "if an account exists" in fp.json()["detail"].lower()
    reset_link = fp.json()["reset_link"]
    assert reset_link, fp.json()
    token = reset_link.split("token=")[1]

    # Unknown email → same generic 200, no link.
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert unknown.status_code == 200
    assert unknown.json()["reset_link"] is None

    # Reset with the token → succeeds and revokes existing sessions.
    r = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "brandnewpw1"})
    assert r.status_code == 200
    # Old refresh token is dead after reset.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    # New password works; old one doesn't.
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "brandnewpw1"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "originalpw1"}).status_code == 401

    # A used/garbage token is rejected.
    assert client.post("/api/v1/auth/reset-password", json={"token": "garbage", "new_password": "whatever123"}).status_code == 400


def test_seeded_admin_is_verified(client):
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@flowcare.ai", "password": "admin12345"},
    ).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["email_verified"] is True
    assert me["organization_name"]


def test_login_lockout(client):
    email = _email()
    client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Lock Clinic", "email": email, "password": "correct-horse"},
    )
    # 5 wrong attempts → account locks (423) on the 6th.
    for _ in range(5):
        bad = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert bad.status_code == 401
    locked = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse"})
    assert locked.status_code == 423  # even the correct password is locked out


def test_refresh_rotation_and_reuse_detection(client):
    email = _email()
    tokens = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Rotate Clinic", "email": email, "password": "rotate-me-123"},
    ).json()
    old_refresh = tokens["refresh_token"]

    # Rotate: get a new refresh token; the old one is now revoked.
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh != old_refresh

    # New token works.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh}).status_code == 200

    # Replaying the OLD (revoked) token is reuse → 401 and the family is revoked,
    # so the previously-valid new token is now dead too.
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert "reuse" in reuse.json()["detail"].lower()
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401  # whole family revoked


def test_logout_revokes_refresh(client):
    email = _email()
    tokens = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Logout Clinic", "email": email, "password": "byebye-123"},
    ).json()
    assert client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    # Refresh after logout fails.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_change_password_revokes_sessions(client):
    email = _email()
    tokens = client.post(
        "/api/v1/auth/signup",
        json={"organization_name": "Pw Clinic", "email": email, "password": "oldpassword1"},
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Wrong current password rejected.
    assert client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "nope", "new_password": "newpassword1"},
    ).status_code == 400

    # Correct change returns fresh tokens and revokes the old refresh token.
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "oldpassword1", "new_password": "newpassword1"},
    )
    assert changed.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    # New password logs in.
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "newpassword1"}).status_code == 200
