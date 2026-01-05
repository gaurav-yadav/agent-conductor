"""Detect interactive prompts from workers and notify supervisors."""

from __future__ import annotations

import logging
from typing import Optional

from agent_conductor.models.session import Session
from agent_conductor.models.terminal import Terminal
from agent_conductor.providers.manager import UnknownProviderError
from agent_conductor.services.inbox_service import InboxService
from agent_conductor.services.session_service import SessionService
from agent_conductor.services.terminal_service import TerminalService

LOG = logging.getLogger(__name__)


class PromptWatcher:
    """Poll providers for interactive prompts and forward them to supervisors."""

    def __init__(
        self,
        session_service: SessionService,
        terminal_service: TerminalService,
        inbox_service: InboxService,
    ) -> None:
        self.sessions = session_service
        self.terminals = terminal_service
        self.inbox = inbox_service

    def scan(self) -> None:
        """Scan all sessions for workers awaiting interactive approval."""
        for session in self.sessions.list_sessions():
            supervisor = self._locate_supervisor(session)
            if not supervisor:
                continue

            for terminal in session.terminals:
                if terminal.id == supervisor.id:
                    continue
                self._notify_if_prompt(supervisor, terminal)

    @staticmethod
    def _locate_supervisor(session: Session) -> Optional[Terminal]:
        for terminal in session.terminals:
            if terminal.window_name.startswith("supervisor-"):
                return terminal
        return None

    def _notify_if_prompt(self, supervisor: Terminal, worker: Terminal) -> None:
        try:
            provider = self.terminals.providers.get_provider(worker.id)
        except UnknownProviderError:  # pragma: no cover - provider may not be loaded yet
            return

        prompt_text = provider.detect_interactive_prompt()
        if not prompt_text:
            return

        message = (
            f"[PROMPT] {worker.window_name} is awaiting input:\n"
            f"{prompt_text}\n"
            f"Respond via: acd send {worker.id} --message \"<choice>\""
        )

        try:
            self.inbox.queue_message(sender_id=worker.id, receiver_id=supervisor.id, message=message)
        except Exception:  # pragma: no cover - defensive logging
            LOG.exception("Failed to queue prompt notification from %s to %s", worker.id, supervisor.id)
