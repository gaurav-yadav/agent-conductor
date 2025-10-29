"""Scheduled flow service."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from agent_conductor.clients.database import Flow as FlowORM, session_scope
from agent_conductor.models.flow import Flow


class FlowService:
    """Persists and manages flow definitions."""

    def register_flow(
        self,
        name: str,
        file_path: str,
        schedule: str,
        agent_profile: str,
        script: Optional[str] = None,
    ) -> Flow:
        flow = FlowORM(
            name=name,
            file_path=file_path,
            schedule=schedule,
            agent_profile=agent_profile,
            script=script,
            enabled=True,
        )
        with session_scope() as db:
            db.merge(flow)
        return Flow.model_validate(flow, from_attributes=True)

    def list_flows(self) -> List[Flow]:
        with session_scope() as db:
            flows = db.query(FlowORM).order_by(FlowORM.name.asc()).all()
            return [Flow.model_validate(obj, from_attributes=True) for obj in flows]

    def get_flow(self, name: str) -> Optional[Flow]:
        with session_scope() as db:
            flow = db.get(FlowORM, name)
            return Flow.model_validate(flow, from_attributes=True) if flow else None

    def set_enabled(self, name: str, enabled: bool) -> None:
        with session_scope() as db:
            flow = db.get(FlowORM, name)
            if flow:
                flow.enabled = enabled

    def delete_flow(self, name: str) -> None:
        with session_scope() as db:
            flow = db.get(FlowORM, name)
            if flow:
                db.delete(flow)

    def record_run(self, name: str, *, last_run: datetime, next_run: Optional[datetime]) -> None:
        with session_scope() as db:
            flow = db.get(FlowORM, name)
            if flow:
                flow.last_run = last_run
                flow.next_run = next_run
