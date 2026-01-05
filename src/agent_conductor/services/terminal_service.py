"""Terminal orchestration service."""

from __future__ import annotations

import logging
import shlex
from typing import List, Optional

from agent_conductor import constants
from agent_conductor.clients.database import Terminal as TerminalORM, session_scope
from agent_conductor.clients.tmux import TmuxClient, TmuxError
from agent_conductor.models.enums import TerminalStatus
from agent_conductor.models.terminal import Terminal as TerminalModel
from agent_conductor.providers.base import ProviderInitializationError
from agent_conductor.providers.manager import ProviderManager
from agent_conductor.utils.pathing import ensure_runtime_directories
from agent_conductor.utils.terminal import generate_session_name, generate_terminal_id, window_name

LOG = logging.getLogger(__name__)


class TerminalService:
    """Business logic for managing terminals."""

    def __init__(self, tmux: Optional[TmuxClient] = None, providers: Optional[ProviderManager] = None) -> None:
        self.tmux = tmux or TmuxClient()
        self.providers = providers or ProviderManager(self.tmux)
        ensure_runtime_directories()

    def create_terminal(
        self,
        provider_key: str,
        role: str,
        agent_profile: Optional[str],
        session_name: Optional[str] = None,
        working_directory: Optional[str] = None,
    ) -> TerminalModel:
        """Create a terminal, spawning a new tmux session if needed."""
        terminal_id = generate_terminal_id()
        target_session = session_name or generate_session_name()
        window = window_name(role, agent_profile, provider_key)
        environment = {constants.TERMINAL_ENV_VAR: terminal_id}

        if session_name is None:
            self.tmux.create_session(
                target_session, window, environment=environment, start_directory=working_directory
            )
        else:
            self.tmux.create_window(
                target_session, window, environment=environment, start_directory=working_directory
            )

        self._pipe_logs(target_session, window, terminal_id)

        try:
            self.providers.create_provider(
                provider_key=provider_key,
                terminal_id=terminal_id,
                session_name=target_session,
                window_name=window,
                agent_profile=agent_profile,
            )
        except ProviderInitializationError:
            self.tmux.kill_window(target_session, window)
            raise

        db_obj = TerminalORM(
            id=terminal_id,
            session_name=target_session,
            window_name=window,
            provider=provider_key,
            agent_profile=agent_profile,
            status=TerminalStatus.READY,
        )
        with session_scope() as db:
            db.add(db_obj)

        return TerminalModel.model_validate(db_obj, from_attributes=True)

    def get_terminal(self, terminal_id: str) -> Optional[TerminalModel]:
        """Return terminal metadata if it exists."""
        with session_scope() as db:
            terminal = db.get(TerminalORM, terminal_id)
            if not terminal:
                return None
            return TerminalModel.model_validate(terminal, from_attributes=True)

    def list_terminals(self, session_name: str) -> List[TerminalModel]:
        with session_scope() as db:
            results = (
                db.query(TerminalORM)
                .filter(TerminalORM.session_name == session_name)
                .order_by(TerminalORM.created_at.asc())
                .all()
            )
            return [TerminalModel.model_validate(obj, from_attributes=True) for obj in results]

    def send_input(self, terminal_id: str, message: str) -> None:
        provider = self.providers.get_provider(terminal_id)
        provider.send_input(message)
        self._update_status(terminal_id, provider.get_status())

    def capture_output(self, terminal_id: str, last_only: bool = False) -> str:
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            raise RuntimeError(f"Terminal '{terminal_id}' not found.")
        history = self.tmux.capture_pane(terminal.session_name, terminal.window_name)
        if last_only:
            provider = self.providers.get_provider(terminal_id)
            return provider.extract_last_message_from_history(history)
        return history

    def delete_terminal(self, terminal_id: str) -> None:
        terminal = self.get_terminal(terminal_id)
        if not terminal:
            return

        # Clean up provider and tmux window
        self.providers.cleanup_provider(terminal_id)
        try:
            self.tmux.kill_window(terminal.session_name, terminal.window_name)
        except TmuxError:
            LOG.warning(
                "tmux window %s/%s already missing during delete_terminal(%s)",
                terminal.session_name,
                terminal.window_name,
                terminal_id,
            )

        with session_scope() as db:
            orm_terminal = db.get(TerminalORM, terminal_id)
            if orm_terminal:
                session = orm_terminal.session_name
                db.delete(orm_terminal)
                db.flush()
                remaining = (
                    db.query(TerminalORM)
                    .filter(TerminalORM.session_name == session)
                    .count()
                )
            else:
                session = terminal.session_name
                remaining = 0

        if remaining == 0:
            try:
                self.tmux.kill_session(session)
            except TmuxError:
                LOG.debug(
                    "tmux session %s already missing while cleaning up terminal %s",
                    session,
                    terminal_id,
                )

    def _update_status(self, terminal_id: str, status: TerminalStatus) -> None:
        with session_scope() as db:
            terminal = db.get(TerminalORM, terminal_id)
            if not terminal:
                return
            terminal.status = status

    def _pipe_logs(self, session_name: str, window_name: str, terminal_id: str) -> None:
        log_path = constants.TERMINAL_LOG_DIR / f"{terminal_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        command = f"cat >> {shlex.quote(str(log_path))}"
        self.tmux.pipe_pane(session_name, window_name, command)
