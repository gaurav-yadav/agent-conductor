"""Cleanup utilities for stale terminals and logs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_conductor import constants
from agent_conductor.clients.database import Terminal as TerminalORM, session_scope
from agent_conductor.models.enums import TerminalStatus
from agent_conductor.services.terminal_service import TerminalService


class CleanupService:
    """Removes stale resources."""

    def __init__(self, terminal_service: TerminalService, retention_days: int = 7) -> None:
        self.terminals = terminal_service
        self.retention = timedelta(days=retention_days)

    def purge_completed_terminals(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.retention
        with session_scope() as db:
            terminals = (
                db.query(TerminalORM)
                .filter(
                    TerminalORM.status.in_(
                        [TerminalStatus.COMPLETED, TerminalStatus.ERROR]
                    ),
                    TerminalORM.created_at <= cutoff,
                )
                .all()
            )
        for terminal in terminals:
            self.terminals.delete_terminal(terminal.id)

    def purge_orphan_logs(self) -> None:
        """Remove log files without a matching terminal record."""
        with session_scope() as db:
            existing_ids = {row[0] for row in db.query(TerminalORM.id).all()}
        log_dir = constants.TERMINAL_LOG_DIR
        if not log_dir.exists():
            return
        for path in log_dir.glob("*.log"):
            terminal_id = path.stem
            if terminal_id not in existing_ids:
                path.unlink(missing_ok=True)
