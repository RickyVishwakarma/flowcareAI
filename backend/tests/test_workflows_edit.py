"""Workflow editor: create, full-graph replace (PUT), validation."""
from __future__ import annotations


def _auth(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@flowcare.ai", "password": "admin12345"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_save_graph(client):
    headers = _auth(client)

    # Create a blank workflow.
    created = client.post(
        "/api/v1/workflows",
        headers=headers,
        json={"name": "Editor Test", "trigger_event": "referral.received", "nodes": []},
    ).json()
    wid = created["id"]
    assert created["version"] == 1

    # Save a real graph from the "editor".
    graph = {
        "name": "Editor Test (saved)",
        "description": "built in the canvas",
        "trigger_event": "referral.received",
        "status": "active",
        "nodes": [
            {"node_key": "t1", "kind": "trigger", "type": "referral.received",
             "config": {}, "next": {"default": "c1"}, "position": {"x": 40, "y": 40}},
            {"node_key": "c1", "kind": "condition", "type": "if",
             "config": {"field": "extracted.insurance_member_id", "op": "exists"},
             "next": {"true": "a1", "false": "a2"}, "position": {"x": 280, "y": 40}},
            {"node_key": "a1", "kind": "action", "type": "verify_insurance",
             "config": {}, "next": {}, "position": {"x": 520, "y": 0}},
            {"node_key": "a2", "kind": "action", "type": "create_task",
             "config": {"title": "Request insurance"}, "next": {}, "position": {"x": 520, "y": 120}},
        ],
    }
    saved = client.put(f"/api/v1/workflows/{wid}", headers=headers, json=graph).json()
    assert saved["name"] == "Editor Test (saved)"
    assert saved["status"] == "active"
    assert saved["version"] == 2  # bumped
    assert len(saved["nodes"]) == 4

    # Re-fetch confirms persistence + positions survived.
    got = client.get(f"/api/v1/workflows/{wid}", headers=headers).json()
    keys = {n["node_key"] for n in got["nodes"]}
    assert keys == {"t1", "c1", "a1", "a2"}
    t1 = next(n for n in got["nodes"] if n["node_key"] == "t1")
    assert t1["position"] == {"x": 40, "y": 40}
    assert t1["next"] == {"default": "c1"}

    # Saving again replaces wholesale (no node duplication). Trim to 2 nodes and
    # clear edges that referenced the removed nodes (no dangling edges allowed).
    graph["nodes"] = graph["nodes"][:2]
    graph["nodes"][0]["next"] = {}
    graph["nodes"][1]["next"] = {}
    again = client.put(f"/api/v1/workflows/{wid}", headers=headers, json=graph).json()
    assert len(again["nodes"]) == 2
    assert again["version"] == 3


def test_dangling_edge_rejected(client):
    headers = _auth(client)
    created = client.post(
        "/api/v1/workflows",
        headers=headers,
        json={"name": "Bad", "trigger_event": "referral.received", "nodes": []},
    ).json()
    r = client.put(
        f"/api/v1/workflows/{created['id']}",
        headers=headers,
        json={
            "name": "Bad", "trigger_event": "referral.received", "status": "draft",
            "nodes": [
                {"node_key": "t1", "kind": "trigger", "type": "referral.received",
                 "config": {}, "next": {"default": "ghost"}, "position": {}},
            ],
        },
    )
    assert r.status_code == 400
    assert "unknown node" in r.json()["detail"]
