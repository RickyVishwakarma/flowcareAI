"""Dashboard analytics endpoint."""
from __future__ import annotations

import io


def _auth(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@flowcare.ai", "password": "admin12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_overview(client):
    headers = _auth(client)

    # Baseline.
    before = client.get("/api/v1/dashboard/overview", headers=headers)
    assert before.status_code == 200, before.text
    base = before.json()
    assert "referrals_total" in base
    assert len(base["referrals_timeseries"]) == 14  # 14-day series
    assert isinstance(base["workflow_success_rate"], float)

    # Process a referral, then the totals move.
    doc = (
        "Patient Name: Sam Park\nDOB: 1991-09-09\n"
        "Insurance Provider: Kaiser\nMember ID: KP-9090\n"
        "Diagnosis: Knee pain\nReason for referral: Orthopedics\n"
    )
    client.post(
        "/api/v1/referrals",
        headers=headers,
        files={"file": ("r.txt", io.BytesIO(doc.encode()), "text/plain")},
    )

    after = client.get("/api/v1/dashboard/overview", headers=headers).json()
    assert after["referrals_total"] == base["referrals_total"] + 1
    # The validated referral shows in the status + validation breakdowns.
    assert sum(after["referrals_by_status"].values()) == after["referrals_total"]
    assert after["referrals_by_source"].get("pdf", 0) >= 0
    # Seeded "Standard Intake" workflow ran → an execution exists.
    assert after["workflow_total"] >= 1
    # Today's bucket incremented.
    assert after["referrals_timeseries"][-1]["count"] >= 1
