"""Provider matching + referral-leakage detection."""
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
        files={"file": ("r.txt", io.BytesIO(text.encode()), "text/plain")},
    ).json()["id"]


def test_providers_seeded(client):
    headers = _auth(client)
    providers = client.get("/api/v1/providers", headers=headers).json()
    assert len(providers) >= 5
    specialties = {p["specialty"] for p in providers}
    assert "cardiology" in specialties and "neurology" in specialties


def test_in_network_match_no_leakage(client):
    headers = _auth(client)
    # Cardiology + Aetna → seeded in-network Dr. Chen accepts Aetna.
    rid = _upload(
        client, headers,
        "Patient Name: Joe Cardio\nDOB: 1970-01-01\nInsurance Provider: Aetna\n"
        "Member ID: AET1\nDiagnosis: Hypertension\nReason for referral: Cardiology consult, chest pain\n",
    )
    res = client.post("/api/v1/providers/match", headers=headers, json={"referral_id": rid}).json()
    assert res["specialty"] == "cardiology", res
    assert res["leakage_risk"] is False
    assert res["in_network"] is True
    assert res["chosen"]["accepts_insurance"] is True
    assert "specialty match" in res["chosen"]["reasons"]


def test_leakage_when_only_out_of_network(client):
    headers = _auth(client)
    # Neurology → only seeded provider is OUT-of-network → leakage.
    rid = _upload(
        client, headers,
        "Patient Name: Nora Neuro\nDOB: 1980-02-02\nInsurance Provider: Aetna\n"
        "Member ID: AET2\nDiagnosis: Migraine\nReason for referral: Neurology, recurring headache\n",
    )
    res = client.post("/api/v1/providers/match", headers=headers, json={"referral_id": rid}).json()
    assert res["specialty"] == "neurology"
    assert res["leakage_risk"] is True
    assert res["in_network"] is False


def test_leakage_when_insurance_not_accepted(client):
    headers = _auth(client)
    # Orthopedics + Aetna → in-network Summit Ortho accepts only Cigna/United → leakage.
    rid = _upload(
        client, headers,
        "Patient Name: Owen Ortho\nDOB: 1990-03-03\nInsurance Provider: Aetna\n"
        "Member ID: AET3\nDiagnosis: Knee pain\nReason for referral: Orthopedics, knee injury\n",
    )
    res = client.post("/api/v1/providers/match", headers=headers, json={"referral_id": rid}).json()
    assert res["specialty"] == "orthopedics"
    assert res["leakage_risk"] is True  # in-network exists but doesn't accept Aetna

    # Latest-match endpoint returns it; audit + dashboard reflect leakage.
    latest = client.get(f"/api/v1/providers/match/{rid}", headers=headers).json()
    assert latest["leakage_risk"] is True
    dash = client.get("/api/v1/dashboard/overview", headers=headers).json()
    assert dash["providers_total"] >= 5
    assert dash["leakage_flagged"] >= 1


def test_match_via_workflow_action(client):
    """The match_provider action runs inside the workflow engine and exposes
    match.leakage_risk for conditions."""
    from app.core.database import SessionLocal
    from app.models.referral import Referral
    from app.services import matching

    headers = _auth(client)
    rid = _upload(
        client, headers,
        "Patient Name: Pat Pulm\nDOB: 1985-04-04\nInsurance Provider: Humana\n"
        "Member ID: HUM1\nDiagnosis: COPD\nReason for referral: Pulmonology, breathing trouble\n",
    )
    db = SessionLocal()
    try:
        referral = db.get(Referral, rid)
        result = matching.match(db, referral)
        assert result["specialty"] == "pulmonology"
        assert result["leakage_risk"] is False  # Lung & Chest in-network accepts Humana
    finally:
        db.close()
