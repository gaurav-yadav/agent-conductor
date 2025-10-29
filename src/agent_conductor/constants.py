"""Shared constants for Agent Conductor."""

from pathlib import Path


HOME_DIR = Path.home() / ".conductor"
LOG_DIR = HOME_DIR / "logs"
TERMINAL_LOG_DIR = LOG_DIR / "terminal"
DB_DIR = HOME_DIR / "db"
DB_FILE = DB_DIR / "conductor.db"
AGENT_STORE_DIR = HOME_DIR / "agent-store"
AGENT_CONTEXT_DIR = HOME_DIR / "agent-context"
FLOWS_DIR = HOME_DIR / "flows"
APPROVALS_DIR = HOME_DIR / "approvals"
SESSION_PREFIX = "conductor-"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9889
TERMINAL_ENV_VAR = "CONDUCTOR_TERMINAL_ID"
