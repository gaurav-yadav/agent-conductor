import json

from click.testing import CliRunner

from agent_conductor.cli.main import cli


def test_launch_with_workers(monkeypatch):
    calls = []

    def fake_request(method, path, payload=None):
        calls.append((method, path, json.loads(json.dumps(payload)) if payload else None))
        if method == "POST" and path == "/sessions":
            return {
                "id": "supervisor-id",
                "session_name": "conductor-1234",
                "window_name": "supervisor-conductor",
                "provider": "claude_code",
                "agent_profile": "conductor",
                "status": "READY",
                "created_at": "2025-01-01T00:00:00",
            }
        if method == "GET" and path == "/sessions/conductor-1234":
            return {
                "name": "conductor-1234",
                "terminals": [
                    {
                        "id": "supervisor-id",
                        "session_name": "conductor-1234",
                        "window_name": "supervisor-conductor",
                        "provider": "claude_code",
                        "agent_profile": "conductor",
                        "status": "READY",
                        "created_at": "2025-01-01T00:00:00",
                    },
                    {
                        "id": "worker-id",
                        "session_name": "conductor-1234",
                        "window_name": "worker-developer",
                        "provider": "claude_code",
                        "agent_profile": "developer",
                        "status": "READY",
                        "created_at": "2025-01-01T00:00:01",
                    },
                ],
            }
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr("agent_conductor.cli.main._request", fake_request)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "launch",
            "--provider",
            "claude_code",
            "--agent-profile",
            "conductor",
            "--with-worker",
            "developer",
        ],
    )

    assert result.exit_code == 0
    post_payload = calls[0][2]
    assert post_payload["workers"] == [
        {"provider": "claude_code", "role": "worker", "agent_profile": "developer"}
    ]
    assert "worker-developer" in result.output
