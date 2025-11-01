"""Provider manager registry."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Type

from agent_conductor.clients.tmux import TmuxClient
from agent_conductor.models.enums import TerminalStatus
from agent_conductor.providers.base import BaseProvider, ProviderInitializationError
from agent_conductor.providers.claude_code import ClaudeCodeProvider
from agent_conductor.providers.codex import CodexProvider
from agent_conductor.providers.q_cli import QCLIProvider

LOG = logging.getLogger(__name__)


class UnknownProviderError(RuntimeError):
    """Raised when a provider key is not registered."""


class ProviderManager:
    """Factory and cache for provider instances keyed by terminal ID."""

    _registry: Dict[str, Type[BaseProvider]] = {
        "q_cli": QCLIProvider,
        "claude_code": ClaudeCodeProvider,
        "codex": CodexProvider,
    }

    def __init__(self, tmux: Optional[TmuxClient] = None) -> None:
        self.tmux = tmux or TmuxClient()
        self._providers: Dict[str, BaseProvider] = {}

    def create_provider(
        self,
        provider_key: str,
        terminal_id: str,
        session_name: str,
        window_name: str,
        agent_profile: Optional[str],
    ) -> BaseProvider:
        if provider_key not in self._registry:
            raise UnknownProviderError(f"Provider '{provider_key}' is not registered.")

        provider_cls = self._registry[provider_key]
        provider = provider_cls(
            terminal_id=terminal_id,
            session_name=session_name,
            window_name=window_name,
            agent_profile=agent_profile,
            tmux=self.tmux,
        )
        try:
            provider.initialize()
        except ProviderInitializationError:
            raise
        self._providers[terminal_id] = provider
        return provider

    def get_provider(self, terminal_id: str) -> BaseProvider:
        if terminal_id not in self._providers:
            raise UnknownProviderError(f"Provider for terminal '{terminal_id}' is not loaded.")
        return self._providers[terminal_id]

    def cleanup_provider(self, terminal_id: str) -> None:
        provider = self._providers.pop(terminal_id, None)
        if provider:
            try:
                provider.cleanup()
            except Exception:  # pragma: no cover - defensive guard
                LOG.warning("Provider cleanup failed for %s", terminal_id, exc_info=True)

    def status(self, terminal_id: str) -> TerminalStatus:
        provider = self.get_provider(terminal_id)
        return provider.get_status()

    def iter_providers(self):
        return self._providers.items()
