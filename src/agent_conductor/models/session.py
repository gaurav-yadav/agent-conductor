"""Session models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from agent_conductor.models.terminal import Terminal


class Session(BaseModel):
    """Aggregated session view."""

    name: str
    terminals: List[Terminal]

    class Config:
        from_attributes = True


class SessionCreateRequest(BaseModel):
    provider: str
    agent_profile: Optional[str] = None
    role: str = "supervisor"
