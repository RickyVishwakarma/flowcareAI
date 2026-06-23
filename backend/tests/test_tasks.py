"""Task inbox: workflow-created tasks, claim, status changes."""
from __future__ import annotations

import io


def _auth(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@flowcare.ai", "password": "admin12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_workflow_creates_task_then_triage(client):
    headers = _auth(client)

    # A referral missing insurance → seeded workflow's false branch creates a task.
    doc = (
        "Patient Name: Lee Adams\nDOB: 1977-07-07\n"
        "Diagnosis: Headache\nReason for referral: Neurology\n"
    )
    client.post(
        "/api/v1/referrals",
        headers=headers,
        files={"file": ("r.txt", io.BytesIO(doc.encode()), "text/plain")},
    )

    tasks = client.get("/api/v1/tasks", headers=headers).json()
    assert len(tasks) >= 1
    task = tasks[0]
    assert task["status"] == "open"
    assert task["assigned_to"] is None

    # Claim it → assigned to me + moves to in_progress.
    claimed = client.post(f"/api/v1/tasks/{task['id']}/claim", headers=headers).json()
    assert claimed["status"] == "in_progress"
    assert claimed["assignee_email"] == "admin@flowcare.ai"

    # "mine" filter now returns it.
    mine = client.get("/api/v1/tasks?mine=true", headers=headers).json()
    assert any(t["id"] == task["id"] for t in mine)

    # Complete it.
    done = client.patch(f"/api/v1/tasks/{task['id']}", headers=headers, json={"status": "done"}).json()
    assert done["status"] == "done"

    # Status filter works.
    open_tasks = client.get("/api/v1/tasks?status_filter=open", headers=headers).json()
    assert all(t["id"] != task["id"] for t in open_tasks)

    # The triage is in the audit trail.
    logs = client.get(f"/api/v1/audit-logs?referral_id={task['referral_id']}", headers=headers).json()
    actions = {r["action"] for r in logs}
    assert "task.claimed" in actions and "task.updated" in actions


def test_manual_task_create(client):
    headers = _auth(client)
    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "Call patient back", "priority": "high"},
    )
    assert created.status_code == 201
    assert created.json()["priority"] == "high"
