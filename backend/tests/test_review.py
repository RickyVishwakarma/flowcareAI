"""Human-in-the-loop review queue tests."""
from __future__ import annotations

import io


def _auth(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@flowcare.ai", "password": "admin12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _upload(client, headers, text):
    return client.post(
        "/api/v1/referrals",
        headers=headers,
        files={"file": ("ref.txt", io.BytesIO(text.encode()), "text/plain")},
    ).json()["id"]


def test_review_flow(client):
    headers = _auth(client)

    # Upload a referral missing insurance provider -> validation FAILED -> needs_review.
    rid = _upload(
        client,
        headers,
        "Patient Name: Maria Lopez\nDOB: 1990-02-02\n"
        "Referring Doctor: Dr. Pena\nDiagnosis: Asthma\n"
        "Reason for referral: Pulmonology consult\n",
    )

    detail = client.get(f"/api/v1/referrals/{rid}", headers=headers).json()
    assert detail["status"] == "needs_review", detail["status"]

    # It shows up in the review queue.
    queue = client.get("/api/v1/review/queue", headers=headers).json()
    assert any(item["id"] == rid for item in queue)
    item = next(i for i in queue if i["id"] == rid)
    assert item["error_count"] >= 1

    # Review detail exposes the OCR text + current fields for correction.
    rdetail = client.get(f"/api/v1/review/{rid}", headers=headers).json()
    assert rdetail["fields"]["patient_name"] == "Maria Lopez"
    assert rdetail["fields"]["insurance_provider"] is None
    assert "Maria Lopez" in (rdetail["ocr_text"] or "")

    # Reviewer corrects the missing insurance info.
    result = client.post(
        f"/api/v1/review/{rid}",
        headers=headers,
        json={
            "insurance_provider": "Cigna",
            "insurance_member_id": "CIG-55512",
            "rerun_workflow": True,
        },
    ).json()
    assert result["validation_status"] in {"passed", "passed_with_warnings"}, result
    assert result["status"] == "validated"
    assert "insurance_provider" in result["changed_fields"]
    assert len(result["workflow_executions"]) >= 1

    # Referral left the queue and the correction persisted.
    queue_after = client.get("/api/v1/review/queue", headers=headers).json()
    assert all(i["id"] != rid for i in queue_after)
    after = client.get(f"/api/v1/referrals/{rid}", headers=headers).json()
    assert after["extracted_data"]["insurance_provider"] == "Cigna"
    assert after["extracted_data"]["extractor"] == "human_review"

    # The review is in the immutable audit trail with the reviewer recorded.
    logs = client.get(f"/api/v1/audit-logs?referral_id={rid}", headers=headers).json()
    reviewed = [r for r in logs if r["action"] == "referral.reviewed"]
    assert reviewed and reviewed[0]["actor"]
    assert "insurance_provider" in reviewed[0]["detail"]["changed_fields"]
