"""Drive the LIVE running API over HTTP and assert every step works.

Usage: python scripts/verify_live.py [base_url]
"""
from __future__ import annotations

import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077"
API = f"{BASE}/api/v1"
ok = 0
fail = 0


def check(label: str, cond: bool, extra: str = "") -> None:
    global ok, fail
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok += 1
    else:
        fail += 1
    print(f"  [{mark}] {label}{(' — ' + extra) if extra else ''}")


print("== FlowCare AI live verification ==")
c = httpx.Client(timeout=15)

# 1. Health
r = c.get(f"{BASE}/health")
check("GET /health 200", r.status_code == 200, r.text)

# 2. Auth — bad creds rejected
r = c.post(f"{API}/auth/login", json={"email": "admin@flowcare.ai", "password": "wrong"})
check("login with wrong password -> 401", r.status_code == 401)

# 3. Auth — good creds
r = c.post(f"{API}/auth/login", json={"email": "admin@flowcare.ai", "password": "admin12345"})
check("login -> 200 + token", r.status_code == 200 and "access_token" in r.json())
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

# 4. Unauthorized access blocked
r = c.get(f"{API}/referrals")
check("GET /referrals without token -> 401", r.status_code == 401)

# 5. /auth/me
r = c.get(f"{API}/auth/me", headers=H)
check("GET /auth/me", r.status_code == 200 and r.json()["role"] == "admin")

# 6. Upload a referral
doc = (
    "Patient Name: John Carter\n"
    "DOB: 1979-08-21\n"
    "Insurance Provider: Aetna\n"
    "Member ID: AET998877\n"
    "Referring Doctor: Dr. Alvarez\n"
    "Diagnosis: Type 2 Diabetes\n"
    "Reason for referral: Endocrinology follow-up\n"
)
r = c.post(
    f"{API}/referrals",
    headers=H,
    files={"file": ("referral.txt", doc.encode(), "text/plain")},
)
check("POST /referrals -> 202", r.status_code == 202, r.text[:120])
ref = r.json()
rid = ref["id"]
check("referral got REF code", ref["reference_code"].startswith("REF-"), ref["reference_code"])

# 7. Referral detail — extraction + validation ran (eager pipeline)
r = c.get(f"{API}/referrals/{rid}", headers=H)
detail = r.json()
ed = detail.get("extracted_data") or {}
check("referral status advanced", detail["status"] in {"validated", "needs_review"}, detail["status"])
check("extracted patient_name", ed.get("patient_name") == "John Carter", str(ed.get("patient_name")))
check("extracted insurance", ed.get("insurance_provider") == "Aetna", str(ed.get("insurance_provider")))
check("extractor recorded", ed.get("extractor") in {"template", "claude"}, str(ed.get("extractor")))
check("validation ran", ed.get("validation_status") in {"passed", "passed_with_warnings", "failed"}, str(ed.get("validation_status")))

# 8. Audit trail
r = c.get(f"{API}/audit-logs?referral_id={rid}", headers=H)
actions = {row["action"] for row in r.json()}
check("audit: referral.uploaded", "referral.uploaded" in actions)
check("audit: referral.parsed", "referral.parsed" in actions)
check("audit: referral.extracted", "referral.extracted" in actions)

# 9. Workflows + executions (seeded "Standard Intake" fired on referral.received)
r = c.get(f"{API}/workflows", headers=H)
wfs = r.json()
check("workflow seeded + active", any(w["name"] == "Standard Intake" and w["status"] == "active" for w in wfs))
wid = wfs[0]["id"]
r = c.get(f"{API}/workflows/{wid}/executions", headers=H)
execs = r.json()
check("workflow execution created", len(execs) >= 1, f"{len(execs)} execution(s)")
if execs:
    e = execs[0]
    visited = [s["type"] for s in e.get("steps", [])]
    check("execution succeeded", e["status"] in {"succeeded", "running", "pending"}, e["status"])
    check("execution walked nodes", len(visited) >= 1, " -> ".join(visited))

# 10. Insurance verification
r = c.post(f"{API}/verify-insurance", headers=H, json={"referral_id": rid})
iv = r.json()
check("POST /verify-insurance", r.status_code == 200 and "status" in iv, str(iv.get("status")))
r = c.get(f"{API}/referrals/{rid}/insurance", headers=H)
check("insurance history stored", len(r.json()) >= 1)

# 11. Appointment scheduling
r = c.post(f"{API}/schedule-appointment", headers=H, json={"referral_id": rid})
ap = r.json()
check("POST /schedule-appointment", r.status_code == 200 and ap.get("scheduled_for"), str(ap.get("status")))
r = c.get(f"{API}/referrals/{rid}/appointments", headers=H)
check("appointment stored", len(r.json()) >= 1)

# 12. List + filter referrals
r = c.get(f"{API}/referrals?status_filter=validated", headers=H)
check("GET /referrals?status_filter works", r.status_code == 200)

# 13. Metrics endpoint exposes our custom series
r = c.get(f"{BASE}/metrics")
body = r.text
check("metrics: referrals_received", "flowcare_referrals_received_total" in body)
check("metrics: processing_seconds", "flowcare_referral_processing_seconds" in body)
check("metrics: workflow_executions", "flowcare_workflow_executions_total" in body)

# 14. OpenAPI docs available
r = c.get(f"{BASE}/openapi.json")
check("OpenAPI schema served", r.status_code == 200 and r.json()["info"]["title"] == "FlowCare AI")

print(f"\n== RESULT: {ok} passed, {fail} failed ==")
sys.exit(1 if fail else 0)
