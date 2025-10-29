"""Thin wrapper around libtmux used by Agent Conductor."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import libtmux
from libtmux.session import Session
from libtmux.window import Window


LOG = logging.getLogger(__name__)


class TmuxError(RuntimeError):
    """Raised when tmux interactions fail."""


class TmuxClient:
    """Minimal helper to encapsulate libtmux operations."""

    def __init__(self) -> None:
        try:
            self._server = libtmux.Server()
        except Exception as exc:  # pragma: no cover - libtmux specific
            raise TmuxError("Unable to connect to tmux server.") from exc

    def session_exists(self, name: str) -> bool:
        """Check if a session already exists."""
        return self._server.has_session(name)

    def create_session(
        self,
        session_name: str,
        window_name: str,
        environment: Optional[Dict[str, str]] = None,
    ) -> Session:
        """Create a new tmux session with an initial window."""
        if self.session_exists(session_name):
            raise TmuxError(f"tmux session '{session_name}' already exists.")

        try:
            session = self._server.new_session(session_name=session_name, attach=False)
        except Exception as exc:  # pragma: no cover - libtmux specific
            raise TmuxError(f"Failed to create tmux session '{session_name}'.") from exc

        window = session.attached_window
        window.rename_window(window_name)
        self._apply_environment(window, environment or {})
        return session

    def create_window(
        self,
        session_name: str,
        window_name: str,
        environment: Optional[Dict[str, str]] = None,
    ) -> Window:
        """Spawn a new window inside an existing session."""
        session = self._get_session(session_name)
        try:
            window = session.new_window(window_name=window_name, attach=False)
        except Exception as exc:  # pragma: no cover - libtmux specific
            raise TmuxError(
                f"Failed to create window '{window_name}' in session '{session_name}'."
            ) from exc

        self._apply_environment(window, environment or {})
        return window

    def kill_session(self, session_name: str) -> None:
        """Terminate a tmux session."""
        if not self.session_exists(session_name):
            return
        session = self._get_session(session_name)
        session.kill_session()

    def kill_window(self, session_name: str, window_name: str) -> None:
        """Terminate a window inside a session."""
        window = self._get_window(session_name, window_name)
        window.kill_window()

    def send_keys(self, session_name: str, window_name: str, keys: str) -> None:
        """Send keystrokes to a specific window."""
        window = self._get_window(session_name, window_name)
        pane = window.attached_pane
        pane.send_keys(keys, enter=True)

    def capture_pane(
        self,
        session_name: str,
        window_name: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> str:
        """Return the textual history for a window."""
        window = self._get_window(session_name, window_name)
        pane = window.attached_pane
        result = pane.capture_pane(
            start=start if start is not None else -1000,
            end=end,
        )
        if isinstance(result, list):
            return "\n".join(result)
        return result or ""

    def pipe_pane(
        self,
        session_name: str,
        window_name: str,
        command: str,
        append: bool = True,
    ) -> None:
        """Pipe pane output to an external command (typically tee into a log file)."""
        window = self._get_window(session_name, window_name)
        pane = window.attached_pane
        # Use cmd() to execute pipe-pane command directly
        flag = "-o" if append else ""
        if flag:
            pane.cmd("pipe-pane", flag, command)
        else:
            pane.cmd("pipe-pane", command)

    def _get_session(self, name: str) -> Session:
        session = self._server.find_where({"session_name": name})
        if session is None:
            raise TmuxError(f"tmux session '{name}' not found.")
        return session

    def _get_window(self, session_name: str, window_name: str) -> Window:
        session = self._get_session(session_name)
        window = session.find_where({"window_name": window_name})
        if window is None:
            raise TmuxError(
                f"tmux window '{window_name}' not found in session '{session_name}'."
            )
        return window

    def _apply_environment(self, window: Window, environment: Dict[str, str]) -> None:
        if not environment:
            return
        pane = window.attached_pane
        for key, value in environment.items():
            try:
                pane.cmd("set-environment", key, value)
            except Exception as exc:  # pragma: no cover - libtmux specific
                LOG.warning("Failed to set tmux environment %s: %s", key, exc)
