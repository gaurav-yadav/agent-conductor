"""Inbox messaging between terminals."""

from __future__ import annotations

from typing import List

from agent_conductor.clients.database import InboxMessage as InboxORM, session_scope
from agent_conductor.models.enums import InboxStatus
from agent_conductor.models.inbox import InboxMessage
from agent_conductor.services.terminal_service import TerminalService


class InboxService:
    """Queues and delivers messages between terminals."""

    def __init__(self, terminal_service: TerminalService) -> None:
        self.terminals = terminal_service

    def queue_message(self, sender_id: str, receiver_id: str, message: str) -> InboxMessage:
        """Persist a message with PENDING status."""
        inbox = InboxORM(
            receiver_id=receiver_id,
            sender_id=sender_id,
            message=message,
            status=InboxStatus.PENDING,
        )
        with session_scope() as db:
            db.add(inbox)
            db.flush()
            db.refresh(inbox)
        return InboxMessage.model_validate(inbox, from_attributes=True)

    def list_messages(self, receiver_id: str) -> List[InboxMessage]:
        with session_scope() as db:
            messages = (
                db.query(InboxORM)
                .filter(InboxORM.receiver_id == receiver_id)
                .order_by(InboxORM.created_at.asc())
                .all()
            )
            return [InboxMessage.model_validate(obj, from_attributes=True) for obj in messages]

    def deliver_pending(self, receiver_id: str) -> None:
        """Attempt to deliver pending messages by injecting them into the receiver terminal."""
        with session_scope() as db:
            pending = (
                db.query(InboxORM)
                .filter(InboxORM.receiver_id == receiver_id, InboxORM.status == InboxStatus.PENDING)
                .order_by(InboxORM.created_at.asc())
                .all()
            )
            for entry in pending:
                formatted = f"[INBOX:{entry.sender_id}] {entry.message}"
                try:
                    self.terminals.send_input(receiver_id, formatted)
                    entry.status = InboxStatus.DELIVERED
                except Exception:  # pragma: no cover - failure path for manual review
                    entry.status = InboxStatus.FAILED

    def mark_failed(self, message_id: int) -> None:
        with session_scope() as db:
            message = db.get(InboxORM, message_id)
            if message:
                message.status = InboxStatus.FAILED

    def deliver_all_pending(self) -> None:
        """Deliver pending messages for every receiver terminal."""
        with session_scope() as db:
            receivers = [
                row[0]
                for row in db.query(InboxORM.receiver_id)
                .filter(InboxORM.status == InboxStatus.PENDING)
                .distinct()
                .all()
            ]
        for receiver_id in receivers:
            self.deliver_pending(receiver_id)
