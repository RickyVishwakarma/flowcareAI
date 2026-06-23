"""End-to-end smoke test of the referral pipeline using SQLite + eager Celery.

Run: pytest -q  (with env from conftest)
"""
from __future__ import annotations

import io


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_and_pipeline(client):
    # 1) Login as the seeded admin.
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@flowcare.ai", "password": "admin12345"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2) Upload a referral document (plain text → no OCR needed).
    referral_text = (
        "Patient Name: Jane Doe\n"
        "DOB: 1985-04-12\n"
        "Insurance Provider: Blue Shield\n"
        "Member ID: BS123456789\n"
        "Referring Doctor: Dr. Smith\n"
        "Diagnosis: Hypertension\n"
        "Reason for referral: Cardiology consult\n"
    )
    resp = client.post(
        "/api/v1/referrals",
        headers=headers,
        files={"file": ("referral.txt", io.BytesIO(referral_text.encode()), "text/plain")},
    )
    assert resp.status_code == 202, resp.text
    referral_id = resp.json()["id"]

    # 3) Pipeline runs eagerly (memory broker) → referral should be validated.
    resp = client.get(f"/api/v1/referrals/{referral_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["status"] in {"validated", "needs_review", "scheduled", "completed"}
    extracted = detail["extracted_data"]
    assert extracted is not None
    assert extracted["patient_name"] == "Jane Doe"
    assert extracted["insurance_provider"] == "Blue Shield"
    assert extracted["validation_status"] in {"passed", "passed_with_warnings", "failed"}

    # 4) Audit trail recorded the lifecycle.
    resp = client.get(f"/api/v1/audit-logs?referral_id={referral_id}", headers=headers)
    assert resp.status_code == 200
    actions = {row["action"] for row in resp.json()}
    assert "referral.uploaded" in actions
    assert "referral.extracted" in actions

    # 5) The seeded workflow fired and produced an execution.
    resp = client.get("/api/v1/workflows", headers=headers)
    workflow_id = resp.json()[0]["id"]
    resp = client.get(f"/api/v1/workflows/{workflow_id}/executions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
