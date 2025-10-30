from agent_conductor.clients.database import ApprovalRequest as ApprovalORM, session_scope
from agent_conductor.models.enums import ApprovalStatus


def test_dashboard_route(api_client):
    response = api_client.get("/dashboard")
    assert response.status_code == 200
    assert "Agent Conductor Dashboard" in response.text


def test_api_session_and_approval_flow(api_client, provider_manager):
    response = api_client.post(
        "/sessions",
        json={
            "provider": "claude_code",
            "role": "supervisor",
            "agent_profile": "conductor",
        },
    )
    assert response.status_code == 201
    conductor = response.json()
    session_name = conductor["session_name"]
    supervisor_id = conductor["id"]

    worker_resp = api_client.post(
        f"/sessions/{session_name}/terminals",
        json={
            "provider": "claude_code",
            "role": "worker",
            "agent_profile": "developer",
        },
    )
    assert worker_resp.status_code == 201
    worker = worker_resp.json()
    worker_id = worker["id"]

    send_resp = api_client.post(
        f"/terminals/{worker_id}/input",
        json={"message": "echo cli", "requires_approval": False},
    )
    assert send_resp.json()["status"] == "sent"

    output = api_client.get(f"/terminals/{worker_id}/output", params={"mode": "last"}).json()[
        "output"
    ]
    assert "echo cli" in output

    approval_resp = api_client.post(
        f"/terminals/{worker_id}/input",
        json={
            "message": "rm -rf /tmp",
            "requires_approval": True,
            "supervisor_id": supervisor_id,
            "metadata_payload": "dangerous",
        },
    )
    data = approval_resp.json()
    assert data["status"] == "queued_for_approval"
    approval_id = data["approval"]["id"]

    approve_resp = api_client.post(f"/approvals/{approval_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"

    provider = provider_manager.providers[worker_id]
    assert provider.sent_messages[-1] == "rm -rf /tmp"

    approvals_list = api_client.get("/approvals", params={"status_filter": "APPROVED"}).json()
    assert any(item["id"] == approval_id for item in approvals_list)

    with session_scope() as db:
        stored = db.get(ApprovalORM, approval_id)
        assert stored.metadata_payload == "dangerous"
        assert stored.status == ApprovalStatus.APPROVED

    delete_worker = api_client.delete(f"/terminals/{worker_id}")
    assert delete_worker.status_code == 204
    assert worker_id not in provider_manager.providers

    delete_conductor = api_client.delete(f"/terminals/{supervisor_id}")
    assert delete_conductor.status_code == 204
