from __future__ import annotations

import asyncio
from typing import Any, List

from fastapi import Depends, FastAPI, HTTPException, status

from agent_conductor.clients.database import init_db
from agent_conductor.models.approval import (
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalRequest,
)
from agent_conductor.models.enums import ApprovalStatus
from agent_conductor.models.flow import Flow, FlowCreateRequest
from agent_conductor.models.inbox import InboxCreateRequest, InboxMessage
from agent_conductor.models.session import Session, SessionCreateRequest
from agent_conductor.models.terminal import (
    Terminal as TerminalModel,
    TerminalCreateRequest,
    TerminalInputRequest,
)
from agent_conductor.providers.base import ProviderInitializationError
from agent_conductor.providers.manager import ProviderManager
from agent_conductor.services.approval_service import ApprovalService
from agent_conductor.services.cleanup_service import CleanupService
from agent_conductor.services.flow_service import FlowService
from agent_conductor.services.inbox_service import InboxService
from agent_conductor.services.prompt_service import PromptWatcher
from agent_conductor.services.session_service import SessionService
from agent_conductor.services.terminal_service import TerminalService
from agent_conductor.utils.logging import setup_logging
from agent_conductor.utils.pathing import ensure_runtime_directories


app = FastAPI(title="Agent Conductor API", version="0.1.0")


def _require_service(name: str):
    service = getattr(app.state, name, None)
    if service is None:
        raise RuntimeError(f"Service '{name}' not initialised.")
    return service


def get_terminal_service() -> TerminalService:
    return _require_service("terminal_service")


def get_session_service() -> SessionService:
    return _require_service("session_service")


def get_inbox_service() -> InboxService:
    return _require_service("inbox_service")


def get_flow_service() -> FlowService:
    return _require_service("flow_service")


def get_approval_service() -> ApprovalService:
    return _require_service("approval_service")


@app.on_event("startup")
async def startup_event() -> None:
    setup_logging()
    ensure_runtime_directories()
    init_db()
    provider_manager = ProviderManager()
    terminal_service = TerminalService(providers=provider_manager)
    inbox_service = InboxService(terminal_service)
    flow_service = FlowService()
    approval_service = ApprovalService(terminal_service, inbox_service)
    session_service = SessionService(terminal_service)
    cleanup_service = CleanupService(terminal_service)
    prompt_watcher = PromptWatcher(session_service, terminal_service, inbox_service)

    app.state.provider_manager = provider_manager
    app.state.terminal_service = terminal_service
    app.state.inbox_service = inbox_service
    app.state.flow_service = flow_service
    app.state.approval_service = approval_service
    app.state.session_service = session_service
    app.state.cleanup_service = cleanup_service
    app.state.prompt_watcher = prompt_watcher
    app.state.background_tasks = [
        asyncio.create_task(_cleanup_loop(cleanup_service)),
        asyncio.create_task(_inbox_loop(inbox_service)),
        asyncio.create_task(_prompt_loop(prompt_watcher)),
    ]


async def _cleanup_loop(cleanup_service: CleanupService) -> None:
    while True:
        cleanup_service.purge_completed_terminals()
        cleanup_service.purge_orphan_logs()
        await asyncio.sleep(3600)


async def _inbox_loop(inbox_service: InboxService) -> None:
    while True:
        inbox_service.deliver_all_pending()
        await asyncio.sleep(5)


async def _prompt_loop(prompt_watcher: PromptWatcher) -> None:
    while True:
        prompt_watcher.scan()
        await asyncio.sleep(3)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    tasks = getattr(app.state, "background_tasks", [])
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


@app.get("/health")
async def health() -> dict[str, str]:
    """Lightweight health probe."""
    return {"status": "ok"}


@app.post("/sessions", response_model=TerminalModel, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreateRequest,
    terminals: TerminalService = Depends(get_terminal_service),
) -> TerminalModel:
    created_workers: list[TerminalModel] = []
    supervisor: TerminalModel | None = None
    try:
        supervisor = terminals.create_terminal(
            provider_key=payload.provider,
            role=payload.role,
            agent_profile=payload.agent_profile,
        )

        for worker_request in payload.workers:
            created_workers.append(
                terminals.create_terminal(
                    provider_key=worker_request.provider,
                    role=worker_request.role,
                    agent_profile=worker_request.agent_profile,
                    session_name=supervisor.session_name,
                )
            )

        return supervisor
    except ProviderInitializationError as exc:
        # Cleanup any partially created terminals to keep state consistent.
        for worker_terminal in created_workers:
            terminals.delete_terminal(worker_terminal.id)
        if supervisor is not None:
            terminals.delete_terminal(supervisor.id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/sessions", response_model=List[Session])
async def list_sessions(
    sessions: SessionService = Depends(get_session_service),
) -> List[Session]:
    return sessions.list_sessions()


@app.get("/sessions/{session_name}", response_model=Session)
async def get_session(
    session_name: str,
    sessions: SessionService = Depends(get_session_service),
) -> Session:
    session_models = sessions.list_sessions()
    for session in session_models:
        if session.name == session_name:
            return session
    raise HTTPException(status_code=404, detail="Session not found.")


@app.delete("/sessions/{session_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_name: str,
    sessions: SessionService = Depends(get_session_service),
) -> None:
    sessions.delete_session(session_name)


@app.post(
    "/sessions/{session_name}/terminals",
    response_model=TerminalModel,
    status_code=status.HTTP_201_CREATED,
)
async def create_worker_terminal(
    session_name: str,
    payload: TerminalCreateRequest,
    terminals: TerminalService = Depends(get_terminal_service),
) -> TerminalModel:
    try:
        return terminals.create_terminal(
            provider_key=payload.provider,
            role=payload.role,
            agent_profile=payload.agent_profile,
            session_name=session_name,
        )
    except ProviderInitializationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/terminals/{terminal_id}", response_model=TerminalModel)
async def get_terminal(
    terminal_id: str,
    terminals: TerminalService = Depends(get_terminal_service),
) -> TerminalModel:
    terminal = terminals.get_terminal(terminal_id)
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal not found.")
    return terminal


@app.post("/terminals/{terminal_id}/input")
async def send_terminal_input(
    terminal_id: str,
    payload: TerminalInputRequest,
    terminals: TerminalService = Depends(get_terminal_service),
    approvals: ApprovalService = Depends(get_approval_service),
) -> dict[str, Any]:
    if payload.requires_approval:
        if not payload.supervisor_id:
            raise HTTPException(status_code=400, detail="supervisor_id is required when requesting approval.")
        approval = approvals.request_approval(
            terminal_id=terminal_id,
            supervisor_id=payload.supervisor_id,
            command_text=payload.message,
            metadata_payload=payload.metadata_payload,
        )
        return {"status": "queued_for_approval", "approval": approval.model_dump()}
    terminals.send_input(terminal_id, payload.message)
    return {"status": "sent"}


@app.get("/terminals/{terminal_id}/output")
async def get_terminal_output(
    terminal_id: str,
    mode: str = "full",
    terminals: TerminalService = Depends(get_terminal_service),
) -> dict[str, str]:
    last_only = mode == "last"
    output = terminals.capture_output(terminal_id, last_only=last_only)
    return {"output": output}


@app.delete("/terminals/{terminal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_terminal(
    terminal_id: str,
    terminals: TerminalService = Depends(get_terminal_service),
) -> None:
    terminals.delete_terminal(terminal_id)


@app.post("/inbox", response_model=InboxMessage, status_code=status.HTTP_201_CREATED)
async def enqueue_message(
    payload: InboxCreateRequest,
    inbox: InboxService = Depends(get_inbox_service),
) -> InboxMessage:
    return inbox.queue_message(
        sender_id=payload.sender_id,
        receiver_id=payload.receiver_id,
        message=payload.message,
    )


@app.get("/inbox/{terminal_id}", response_model=List[InboxMessage])
async def list_inbox(
    terminal_id: str,
    inbox: InboxService = Depends(get_inbox_service),
) -> List[InboxMessage]:
    return inbox.list_messages(terminal_id)


@app.post("/inbox/{terminal_id}/deliver", status_code=status.HTTP_202_ACCEPTED)
async def deliver_inbox(
    terminal_id: str,
    inbox: InboxService = Depends(get_inbox_service),
) -> None:
    inbox.deliver_pending(terminal_id)


@app.post("/flows", response_model=Flow, status_code=status.HTTP_201_CREATED)
async def register_flow(
    payload: FlowCreateRequest,
    flows: FlowService = Depends(get_flow_service),
) -> Flow:
    return flows.register_flow(
        name=payload.name,
        file_path=payload.file_path,
        schedule=payload.schedule,
        agent_profile=payload.agent_profile,
        script=payload.script,
    )


@app.get("/flows", response_model=List[Flow])
async def list_flows(
    flows: FlowService = Depends(get_flow_service),
) -> List[Flow]:
    return flows.list_flows()


@app.get("/flows/{name}", response_model=Flow)
async def get_flow(
    name: str,
    flows: FlowService = Depends(get_flow_service),
) -> Flow:
    flow = flows.get_flow(name)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found.")
    return flow


@app.post("/flows/{name}/enable", status_code=status.HTTP_202_ACCEPTED)
async def enable_flow(
    name: str,
    flows: FlowService = Depends(get_flow_service),
) -> None:
    flows.set_enabled(name, True)


@app.post("/flows/{name}/disable", status_code=status.HTTP_202_ACCEPTED)
async def disable_flow(
    name: str,
    flows: FlowService = Depends(get_flow_service),
) -> None:
    flows.set_enabled(name, False)


@app.delete("/flows/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    name: str,
    flows: FlowService = Depends(get_flow_service),
) -> None:
    flows.delete_flow(name)


@app.post("/approvals", response_model=ApprovalRequest, status_code=status.HTTP_201_CREATED)
async def request_approval(
    payload: ApprovalCreateRequest,
    approvals: ApprovalService = Depends(get_approval_service),
) -> ApprovalRequest:
    return approvals.request_approval(
        terminal_id=payload.terminal_id,
        supervisor_id=payload.supervisor_id,
        command_text=payload.command_text,
        metadata_payload=payload.metadata_payload,
    )


@app.get("/approvals", response_model=List[ApprovalRequest])
async def list_approvals(
    status_filter: ApprovalStatus | None = None,
    approvals: ApprovalService = Depends(get_approval_service),
) -> List[ApprovalRequest]:
    return approvals.list_requests(status_filter)


@app.post("/approvals/{request_id}/approve", response_model=ApprovalRequest)
async def approve_request(
    request_id: int,
    approvals: ApprovalService = Depends(get_approval_service),
) -> ApprovalRequest:
    return approvals.approve(request_id)


@app.post("/approvals/{request_id}/deny", response_model=ApprovalRequest)
async def deny_request(
    request_id: int,
    payload: ApprovalDecisionRequest,
    approvals: ApprovalService = Depends(get_approval_service),
) -> ApprovalRequest:
    return approvals.deny(request_id, reason=payload.reason)
