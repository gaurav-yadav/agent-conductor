"""Agent profile loading helpers."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Optional

import frontmatter

from agent_conductor import constants
from agent_conductor.models.agent_profile import AgentProfile


class AgentProfileError(RuntimeError):
    """Raised when an agent profile cannot be loaded or parsed."""


def _load_profile_file(path: Path) -> Optional[AgentProfile]:
    """Return an AgentProfile if the markdown file exists."""
    if not path.exists():
        return None

    post = frontmatter.loads(path.read_text())
    metadata = dict(post.metadata)
    metadata["body"] = post.content.strip()
    return AgentProfile(**metadata)


def load_agent_profile(name: str) -> AgentProfile:
    """Load an agent profile from the runtime context or bundled store."""
    try:
        local_profile = constants.AGENT_CONTEXT_DIR / f"{name}.md"
        profile = _load_profile_file(local_profile)
        if profile is not None:
            return profile

        try:
            bundled_file = resources.files("agent_conductor.agent_store") / f"{name}.md"
        except FileNotFoundError as exc:
            raise AgentProfileError(f"Agent profile '{name}' not found in bundled store.") from exc

        if not bundled_file.is_file():
            raise AgentProfileError(f"Agent profile '{name}' not found.")

        post = frontmatter.loads(bundled_file.read_text())
        metadata = dict(post.metadata)
        metadata["body"] = post.content.strip()
        return AgentProfile(**metadata)

    except Exception as exc:
        raise AgentProfileError(f"Failed to load agent profile '{name}': {exc}") from exc
