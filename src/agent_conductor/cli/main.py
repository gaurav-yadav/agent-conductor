from __future__ import annotations

import json
from typing import Any, Dict, Optional

import click
import httpx

from agent_conductor.clients.database import init_db
from agent_conductor.utils import agent_profiles
from agent_conductor.utils.logging import setup_logging
from agent_conductor.utils.pathing import ensure_runtime_directories

API_BASE = "http://127.0.0.1:9889"


def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=60) as client:
        response = client.request(method, url, json=payload)
    if response.status_code >= 400:
        raise click.ClickException(f"API error {response.status_code}: {response.text}")
    if response.content:
        return response.json()
    return None


@click.group(help="Agent Conductor command-line interface.")
def cli() -> None:
    """Root command for Agent Conductor."""
    setup_logging()


@cli.command()
def init() -> None:
    """Initialize local directories and database."""
    ensure_runtime_directories()
    init_db()
    click.echo("Agent Conductor environment initialized.")


@cli.command()
@click.argument("source")
@click.option("--name", help="Override the stored filename (defaults to source name).")
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    default="user",
    show_default=True,
    help="Install into the global user store or the project-local .conductor directory.",
)
@click.option("--force/--no-force", default=False, show_default=True, help="Overwrite existing file.")
def install(source: str, name: Optional[str], scope: str, force: bool) -> None:
    """Install an agent persona from bundled profiles or a local file."""
    try:
        result = agent_profiles.install_agent_profile(
            source, name=name, scope=scope, force=force  # type: ignore[arg-type]
        )
    except agent_profiles.AgentProfileError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.option("--provider", required=True, help="Provider key (e.g., claude_code).")
@click.option("--agent-profile", help="Agent profile name used for the terminal.")
@click.option("--role", default="supervisor", show_default=True, help="Role for window naming.")
def launch(provider: str, agent_profile: Optional[str], role: str) -> None:
    """Launch a new session with a supervisor terminal."""
    payload = {
        "provider": provider,
        "agent_profile": agent_profile,
        "role": role,
    }
    result = _request("POST", "/sessions", payload)
    click.echo(json.dumps(result, indent=2))


@cli.command("sessions")
def list_sessions() -> None:
    """List active sessions."""
    result = _request("GET", "/sessions")
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.argument("session_name")
@click.option("--provider", required=True, help="Provider key for the worker (e.g., claude_code).")
@click.option("--agent-profile", help="Agent profile for the worker.")
@click.option("--role", default="worker", show_default=True, help="Role label.")
def worker(session_name: str, provider: str, agent_profile: Optional[str], role: str) -> None:
    """Spawn a worker terminal inside an existing session."""
    payload = {
        "provider": provider,
        "agent_profile": agent_profile,
        "role": role,
    }
    result = _request("POST", f"/sessions/{session_name}/terminals", payload)
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.argument("terminal_id")
@click.option("--message", prompt=True, help="Message to send to the terminal.")
@click.option("--require-approval/--no-require-approval", default=False, show_default=True)
@click.option("--supervisor", help="Supervisor terminal ID when requesting approval.")
@click.option("--metadata", help="Optional metadata payload for approval.")
def send(
    terminal_id: str,
    message: str,
    require_approval: bool,
    supervisor: Optional[str],
    metadata: Optional[str],
) -> None:
    """Send input to a terminal."""
    payload: Dict[str, Any] = {"message": message, "requires_approval": require_approval}
    if require_approval:
        if not supervisor:
            raise click.ClickException("Supervisor terminal ID is required when requesting approval.")
        payload["supervisor_id"] = supervisor
        if metadata is not None:
            payload["metadata_payload"] = metadata
    result = _request("POST", f"/terminals/{terminal_id}/input", payload)
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.argument("terminal_id")
@click.option("--mode", type=click.Choice(["full", "last"]), default="full", show_default=True)
def output(terminal_id: str, mode: str) -> None:
    """Fetch terminal output."""
    result = _request("GET", f"/terminals/{terminal_id}/output?mode={mode}")
    click.echo(result["output"])


@cli.command()
@click.argument("terminal_id")
def close(terminal_id: str) -> None:
    """Terminate a terminal."""
    _request("DELETE", f"/terminals/{terminal_id}")
    click.echo("Terminal deleted.")


@cli.command("send-message")
@click.option("--sender", required=True, help="Sender terminal ID.")
@click.option("--receiver", required=True, help="Receiver terminal ID.")
@click.option("--message", prompt=True, help="Message body.")
def send_message(sender: str, receiver: str, message: str) -> None:
    """Queue an inbox message."""
    payload = {"sender_id": sender, "receiver_id": receiver, "message": message}
    result = _request("POST", "/inbox", payload)
    click.echo(json.dumps(result, indent=2))


@cli.command("inbox")
@click.argument("terminal_id")
def inbox(terminal_id: str) -> None:
    """List inbox messages for a terminal."""
    result = _request("GET", f"/inbox/{terminal_id}")
    click.echo(json.dumps(result, indent=2))


@cli.command("approve")
@click.argument("request_id", type=int)
def approve(request_id: int) -> None:
    """Approve a pending command."""
    result = _request("POST", f"/approvals/{request_id}/approve")
    click.echo(json.dumps(result, indent=2))


@cli.command("deny")
@click.argument("request_id", type=int)
@click.option("--reason", help="Reason for denial.")
def deny(request_id: int, reason: Optional[str]) -> None:
    """Deny a pending command."""
    payload = {"reason": reason}
    result = _request("POST", f"/approvals/{request_id}/deny", payload)
    click.echo(json.dumps(result, indent=2))


@cli.command("approvals")
@click.option(
    "--status",
    type=click.Choice(["PENDING", "APPROVED", "DENIED"]),
    help="Optional status filter.",
)
def approvals(status: Optional[str]) -> None:
    """List approval requests."""
    suffix = f"?status_filter={status}" if status else ""
    result = _request("GET", f"/approvals{suffix}")
    click.echo(json.dumps(result, indent=2))


@cli.command("personas")
@click.option("--bundled/--no-bundled", default=True, show_default=True, help="Include bundled personas.")
@click.option(
    "--installed/--no-installed",
    default=True,
    show_default=True,
    help="Include installed personas (user and project scopes).",
)
def personas(bundled: bool, installed: bool) -> None:
    """List available personas from bundled and installed stores."""
    catalog = agent_profiles.get_persona_catalog(
        include_bundled=bundled, include_installed=installed
    )
    click.echo(json.dumps(catalog, indent=2))


@cli.group()
def flow() -> None:
    """Flow management commands."""


@flow.command("register")
@click.option("--name", required=True)
@click.option("--file", "file_path", required=True)
@click.option("--schedule", required=True)
@click.option("--agent-profile", required=True)
@click.option("--script")
def register_flow(name: str, file_path: str, schedule: str, agent_profile: str, script: Optional[str]) -> None:
    payload = {
        "name": name,
        "file_path": file_path,
        "schedule": schedule,
        "agent_profile": agent_profile,
        "script": script,
    }
    result = _request("POST", "/flows", payload)
    click.echo(json.dumps(result, indent=2))


@flow.command("list")
def list_flows() -> None:
    result = _request("GET", "/flows")
    click.echo(json.dumps(result, indent=2))


@flow.command("enable")
@click.argument("name")
def enable_flow(name: str) -> None:
    _request("POST", f"/flows/{name}/enable")
    click.echo("Flow enabled.")


@flow.command("disable")
@click.argument("name")
def disable_flow(name: str) -> None:
    _request("POST", f"/flows/{name}/disable")
    click.echo("Flow disabled.")


@flow.command("remove")
@click.argument("name")
def remove_flow(name: str) -> None:
    _request("DELETE", f"/flows/{name}")
    click.echo("Flow removed.")


if __name__ == "__main__":
    cli()
