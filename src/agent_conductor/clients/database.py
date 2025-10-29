"""SQLite database client for Agent Conductor."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from agent_conductor import constants
from agent_conductor.models.enums import ApprovalStatus, InboxStatus, TerminalStatus
from agent_conductor.utils.pathing import ensure_runtime_directories


class BaseModel(DeclarativeBase):
    """Declarative base class for SQLAlchemy models."""


def _build_engine(echo: bool = False):
    ensure_runtime_directories()
    return create_engine(f"sqlite:///{constants.DB_FILE}", echo=echo, future=True)


ENGINE = _build_engine()
SESSION_FACTORY = sessionmaker(bind=ENGINE, autoflush=False, expire_on_commit=False, future=True)


class Terminal(BaseModel):
    """Represents a tmux window managed by the orchestrator."""

    __tablename__ = "terminals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_name: Mapped[str] = mapped_column(String, nullable=False)
    window_name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    agent_profile: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[TerminalStatus] = mapped_column(Enum(TerminalStatus), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    inbox_messages: Mapped[list["InboxMessage"]] = relationship(
        back_populates="receiver", cascade="all, delete-orphan"
    )


class InboxMessage(BaseModel):
    """Message queued for delivery to a terminal."""

    __tablename__ = "inbox_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    receiver_id: Mapped[str] = mapped_column(String, ForeignKey("terminals.id"), nullable=False)
    sender_id: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[InboxStatus] = mapped_column(Enum(InboxStatus), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    receiver: Mapped["Terminal"] = relationship(back_populates="inbox_messages")


class Flow(BaseModel):
    """Scheduled flow definition."""

    __tablename__ = "flows"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    schedule: Mapped[str] = mapped_column(String, nullable=False)
    agent_profile: Mapped[str] = mapped_column(String, nullable=False)
    script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_run: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApprovalRequest(BaseModel):
    """Queued approval for human-in-the-loop command execution."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    terminal_id: Mapped[str] = mapped_column(String, ForeignKey("terminals.id"), nullable=False)
    supervisor_id: Mapped[str] = mapped_column(String, nullable=False)
    command_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_payload: Mapped[Optional[str]] = mapped_column("metadata", Text, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False
    )
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)


def init_db(echo: bool = False) -> None:
    """Create tables if they do not exist."""
    global ENGINE, SESSION_FACTORY
    ENGINE = _build_engine(echo=echo)
    SESSION_FACTORY = sessionmaker(
        bind=ENGINE,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    BaseModel.metadata.create_all(bind=ENGINE)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SESSION_FACTORY()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
