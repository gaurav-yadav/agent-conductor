"""Claude Code provider integration."""

from __future__ import annotations

import logging
import re
import shlex
import time
from typing import Optional

from agent_conductor.clients.tmux import TmuxError
from agent_conductor.models.enums import TerminalStatus
from agent_conductor.providers.base import BaseProvider, ProviderInitializationError
from agent_conductor.utils.agent_profiles import AgentProfileError, load_agent_profile

ANSI_CODE_PATTERN = r"\x1b\[[0-9;]*m"
RESPONSE_PATTERN = r"⏺(?:\x1b\[[0-9;]*m)*\s+"
PROCESSING_PATTERN = r"[✶✢✽✻·✳].*….*\(esc to interrupt.*\)"
IDLE_PROMPT_PATTERN = r">[\s\xa0]"
WAITING_USER_ANSWER_PATTERN = r"❯.*\d+\."

LOG = logging.getLogger(__name__)


class ClaudeCodeProvider(BaseProvider):
    """Provider that manages the Claude Code CLI inside tmux."""

    def __init__(
        self,
        terminal_id: str,
        session_name: str,
        window_name: str,
        agent_profile: Optional[str],
        tmux,
    ) -> None:
        super().__init__(terminal_id, session_name, window_name, agent_profile, tmux)
        self._initialized = False

    def build_startup_command(self) -> Optional[str]:
        """Not used – command is assembled in initialize."""
        return None

    def _build_claude_command(self) -> list[str]:
        command_parts = ["claude"]

        if self.agent_profile:
            try:
                profile = load_agent_profile(self.agent_profile)
            except AgentProfileError as exc:
                raise ProviderInitializationError(str(exc)) from exc

            prompt_sections = []
            if profile.prompt:
                prompt_sections.append(profile.prompt.strip())
            if profile.body:
                prompt_sections.append(profile.body.strip())
            system_prompt = "\n\n".join(filter(None, prompt_sections)).strip()

            if system_prompt:
                command_parts.extend(["--append-system-prompt", shlex.quote(system_prompt)])

            if profile.mcpServers:
                mcp_json = profile.model_dump_json(include={"mcpServers"})
                command_parts.extend(["--mcp-config", shlex.quote(mcp_json)])

        return command_parts

    def initialize(self) -> None:
        self.ensure_binary_exists("claude")
        command = " ".join(self._build_claude_command())
        self.tmux.send_keys(self.session_name, self.window_name, command)

        if not self._wait_for_status(TerminalStatus.READY, timeout=30.0):
            raise ProviderInitializationError("Claude Code initialization timed out.")

        self._initialized = True
        self._status = TerminalStatus.READY

    def _wait_for_status(
        self, target_status: TerminalStatus, timeout: float, polling_interval: float = 1.0
    ) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_status()
            if status == target_status:
                return True
            time.sleep(polling_interval)
        return False

    def get_status(self) -> TerminalStatus:
        output = self.tmux.capture_pane(self.session_name, self.window_name)

        if not output:
            self._status = TerminalStatus.RUNNING
            return self._status

        if re.search(PROCESSING_PATTERN, output):
            self._status = TerminalStatus.RUNNING
            return self._status

        if re.search(WAITING_USER_ANSWER_PATTERN, output):
            self._status = TerminalStatus.RUNNING
            return self._status

        if re.search(RESPONSE_PATTERN, output) and re.search(IDLE_PROMPT_PATTERN, output):
            self._status = TerminalStatus.COMPLETED
            return self._status

        if re.search(IDLE_PROMPT_PATTERN, output):
            self._status = TerminalStatus.READY
            return self._status

        self._status = TerminalStatus.RUNNING
        return self._status

    def extract_last_message_from_history(self, history: str) -> str:
        matches = list(re.finditer(RESPONSE_PATTERN, history))
        if not matches:
            raise ValueError("No Claude Code response detected in history.")

        start_pos = matches[-1].end()
        remaining_text = history[start_pos:]

        response_lines = []
        for line in remaining_text.splitlines():
            if re.match(r">\s", line) or "────────" in line:
                break
            stripped = line.strip()
            if stripped:
                response_lines.append(stripped)

        if not response_lines:
            raise ValueError("Claude Code response was empty after ⏺ marker.")

        final_answer = "\n".join(response_lines).strip()
        final_answer = re.sub(ANSI_CODE_PATTERN, "", final_answer)
        return final_answer.strip()

    def cleanup(self) -> None:
        if self._initialized:
            try:
                self.tmux.send_keys(self.session_name, self.window_name, "/exit")
            except TmuxError:
                LOG.warning(
                    "Skipping exit command for %s/%s — tmux window no longer exists.",
                    self.session_name,
                    self.window_name,
                )
        self._status = TerminalStatus.COMPLETED
